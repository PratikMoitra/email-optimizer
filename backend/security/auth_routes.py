"""
OAuth and API key management routes.

Provides:
  - Google OAuth2 login/callback (for Google Sheets access)
  - API key CRUD (for OpenAI, Instantly, Vayne, Anymailfinder)
  - Connection status endpoint (which services are connected per user)
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional
from urllib.parse import urlencode

import requests as _requests
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from db import get_db
from models import UserApiKey, UserOAuthToken, Profile
from security.encryption import encrypt, decrypt

log = logging.getLogger("auth")

router = APIRouter()

# ─────────────────────────────────────────────
# Google OAuth2
# ─────────────────────────────────────────────

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",  # to list spreadsheets
    "openid",
    "email",
    "profile",
]

# In-memory state store (for CSRF protection in OAuth flow)
# In production, use Redis or DB-backed sessions
_oauth_states: Dict[str, dict] = {}


@router.get("/auth/google/login")
async def google_login(user_id: str = Query(..., description="Current user ID")):
    """
    Redirect URL for Google OAuth2 authorization.
    Frontend should redirect the user's browser to this URL.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not configured")

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {"user_id": user_id, "created_at": datetime.now(timezone.utc)}

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",  # get refresh_token
        "prompt": "consent",  # force consent screen to always get refresh_token
        "state": state,
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return {"auth_url": auth_url}


@router.get("/auth/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Google OAuth2 callback — exchanges code for tokens, stores them encrypted.
    """
    # Validate state (CSRF protection)
    state_data = _oauth_states.pop(state, None)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    user_id = state_data["user_id"]

    # Exchange authorization code for tokens
    token_response = _requests.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    })

    if token_response.status_code != 200:
        log.error("Google token exchange failed: %s", token_response.text)
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")

    token_data = token_response.json()
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)
    token_expiry = datetime.now(timezone.utc).replace(microsecond=0)
    from datetime import timedelta
    token_expiry += timedelta(seconds=expires_in)

    # Get user info from Google
    userinfo_response = _requests.get(GOOGLE_USERINFO_URL, headers={
        "Authorization": f"Bearer {access_token}",
    })
    google_user = userinfo_response.json() if userinfo_response.status_code == 200 else {}

    # Upsert OAuth token
    existing = db.query(UserOAuthToken).filter(
        UserOAuthToken.user_id == user_id,
        UserOAuthToken.provider == "google",
    ).first()

    if existing:
        existing.access_token = encrypt(access_token)
        if refresh_token:
            existing.refresh_token = encrypt(refresh_token)
        existing.token_expires_at = token_expiry
        existing.scopes = " ".join(GOOGLE_SCOPES)
        existing.provider_metadata = {
            **(existing.provider_metadata or {}),
            "email": google_user.get("email"),
            "name": google_user.get("name"),
        }
        existing.updated_at = datetime.now(timezone.utc)
    else:
        new_token = UserOAuthToken(
            user_id=user_id,
            provider="google",
            access_token=encrypt(access_token),
            refresh_token=encrypt(refresh_token) if refresh_token else None,
            token_expires_at=token_expiry,
            scopes=" ".join(GOOGLE_SCOPES),
            provider_metadata={
                "email": google_user.get("email"),
                "name": google_user.get("name"),
            },
        )
        db.add(new_token)

    db.commit()
    log.info("Google OAuth tokens stored for user %s (%s)", user_id, google_user.get("email"))

    # Redirect to frontend settings page with success
    redirect_url = f"{settings.APP_URL}/?google=connected"
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=redirect_url)


@router.delete("/auth/google/disconnect")
async def google_disconnect(
    user_id: str = Query(..., description="Current user ID"),
    db: Session = Depends(get_db),
):
    """Disconnect Google Sheets — removes stored OAuth tokens."""
    token = db.query(UserOAuthToken).filter(
        UserOAuthToken.user_id == user_id,
        UserOAuthToken.provider == "google",
    ).first()

    if not token:
        raise HTTPException(status_code=404, detail="Google not connected")

    db.delete(token)
    db.commit()
    return {"status": "disconnected", "provider": "google"}


@router.get("/auth/google/sheets")
async def list_google_sheets(
    user_id: str = Query(..., description="Current user ID"),
    db: Session = Depends(get_db),
):
    """List spreadsheets available to the connected Google account."""
    token = db.query(UserOAuthToken).filter(
        UserOAuthToken.user_id == user_id,
        UserOAuthToken.provider == "google",
    ).first()

    if not token:
        raise HTTPException(status_code=404, detail="Google not connected. Please connect first.")

    from services.sheets import get_client_from_oauth_token, list_spreadsheets

    access_token = decrypt(token.access_token)
    refresh_token = decrypt(token.refresh_token) if token.refresh_token else None

    try:
        client, updated = get_client_from_oauth_token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=token.token_expires_at,
        )

        # If token was refreshed, save new token
        if updated:
            token.access_token = encrypt(updated["access_token"])
            if updated.get("token_expires_at"):
                token.token_expires_at = updated["token_expires_at"]
            token.updated_at = datetime.now(timezone.utc)
            db.commit()

        sheets = list_spreadsheets(client)
        selected_sheet_id = (token.provider_metadata or {}).get("sheet_id")

        return {
            "sheets": sheets,
            "selected_sheet_id": selected_sheet_id,
        }
    except Exception as e:
        log.error("Failed to list Google Sheets: %s", e)
        raise HTTPException(status_code=500, detail=f"Google Sheets API error: {str(e)}")


class SelectSheetRequest(BaseModel):
    user_id: str
    sheet_id: str
    sheet_name: Optional[str] = None


@router.post("/auth/google/sheets/select")
async def select_google_sheet(
    req: SelectSheetRequest,
    db: Session = Depends(get_db),
):
    """Set which Google Sheet to sync leads to for this user."""
    token = db.query(UserOAuthToken).filter(
        UserOAuthToken.user_id == req.user_id,
        UserOAuthToken.provider == "google",
    ).first()

    if not token:
        raise HTTPException(status_code=404, detail="Google not connected")

    metadata = token.provider_metadata or {}
    metadata["sheet_id"] = req.sheet_id
    if req.sheet_name:
        metadata["sheet_name"] = req.sheet_name
    token.provider_metadata = metadata
    token.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "selected", "sheet_id": req.sheet_id, "sheet_name": req.sheet_name}


# ─────────────────────────────────────────────
# API Key Management (OpenAI, Instantly, etc.)
# ─────────────────────────────────────────────

ALLOWED_SERVICES = {"openai", "instantly", "vayne", "anymailfinder"}


class SaveApiKeyRequest(BaseModel):
    user_id: str
    service: str
    api_key: str


@router.post("/auth/api-keys")
async def save_api_key(
    req: SaveApiKeyRequest,
    db: Session = Depends(get_db),
):
    """Save (or update) an API key for a service. Key is encrypted at rest."""
    if req.service not in ALLOWED_SERVICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service. Allowed: {', '.join(sorted(ALLOWED_SERVICES))}",
        )

    existing = db.query(UserApiKey).filter(
        UserApiKey.user_id == req.user_id,
        UserApiKey.service == req.service,
    ).first()

    encrypted = encrypt(req.api_key)

    if existing:
        existing.encrypted_key = encrypted
        existing.created_at = datetime.now(timezone.utc)
    else:
        new_key = UserApiKey(
            user_id=req.user_id,
            service=req.service,
            encrypted_key=encrypted,
        )
        db.add(new_key)

    db.commit()
    log.info("API key saved for user %s, service %s", req.user_id, req.service)

    return {"status": "saved", "service": req.service}


@router.delete("/auth/api-keys/{service}")
async def delete_api_key(
    service: str,
    user_id: str = Query(..., description="Current user ID"),
    db: Session = Depends(get_db),
):
    """Remove a stored API key."""
    key = db.query(UserApiKey).filter(
        UserApiKey.user_id == user_id,
        UserApiKey.service == service,
    ).first()

    if not key:
        raise HTTPException(status_code=404, detail=f"No key found for {service}")

    db.delete(key)
    db.commit()
    return {"status": "deleted", "service": service}


# ─────────────────────────────────────────────
# Connection Status
# ─────────────────────────────────────────────

@router.get("/auth/status")
async def connection_status(
    user_id: str = Query(..., description="Current user ID"),
    db: Session = Depends(get_db),
):
    """
    Get the connection status of all services for a user.
    Returns which services are connected and basic metadata.
    """
    # OAuth tokens (Google, eventually OpenAI)
    oauth_tokens = db.query(UserOAuthToken).filter(
        UserOAuthToken.user_id == user_id,
    ).all()

    oauth_status = {}
    for t in oauth_tokens:
        oauth_status[t.provider] = {
            "connected": True,
            "email": (t.provider_metadata or {}).get("email"),
            "sheet_id": (t.provider_metadata or {}).get("sheet_id"),
            "sheet_name": (t.provider_metadata or {}).get("sheet_name"),
            "expires_at": t.token_expires_at.isoformat() if t.token_expires_at else None,
        }

    # API keys
    api_keys = db.query(UserApiKey).filter(
        UserApiKey.user_id == user_id,
    ).all()

    api_key_status = {}
    for k in api_keys:
        api_key_status[k.service] = {
            "connected": True,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            # Never expose the actual key — just confirm it exists
            "key_preview": decrypt(k.encrypted_key)[:8] + "..." if k.encrypted_key else None,
        }

    return {
        "oauth": oauth_status,
        "api_keys": api_key_status,
        "services": {
            "google": oauth_status.get("google", {"connected": False}),
            "openai": api_key_status.get("openai", {"connected": False}),
            "instantly": api_key_status.get("instantly", {"connected": False}),
            "vayne": api_key_status.get("vayne", {"connected": False}),
            "anymailfinder": api_key_status.get("anymailfinder", {"connected": False}),
        },
    }
