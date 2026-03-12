"""
SQLAlchemy ORM models — mirrors the PostgreSQL schema.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.orm import relationship
from db import Base


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True)  # UUID from Supabase auth (or manual on staging)
    email = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, default="pending")  # pending | user | admin
    approved_at = Column(DateTime(timezone=True))
    webhook_url = Column(Text)
    webhook_secret = Column(String)
    notification_time = Column(String, default="09:00")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    api_keys = relationship("UserApiKey", back_populates="user", cascade="all, delete-orphan")
    batches = relationship("Batch", back_populates="user", cascade="all, delete-orphan")


class UserApiKey(Base):
    __tablename__ = "user_api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    service = Column(String, nullable=False)  # vayne | anymailfinder | instantly | openai | google_sheets
    encrypted_key = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("Profile", back_populates="api_keys")

    __table_args__ = (
        Index("uq_user_service", "user_id", "service", unique=True),
    )


class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, default="scraping")  # scraping|validating|researching|generating|deploying|complete|paused
    vayne_order_id = Column(Integer)
    instantly_campaign_id = Column(String)
    sales_nav_url = Column(Text)
    total_leads = Column(Integer, default=0)
    leads_validated = Column(Integer, default=0)
    leads_valid = Column(Integer, default=0)
    leads_researched = Column(Integer, default=0)
    leads_generated = Column(Integer, default=0)
    leads_deployed = Column(Integer, default=0)
    credits_used = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("Profile", back_populates="batches")
    leads = relationship("Lead", back_populates="batch", cascade="all, delete-orphan")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)

    # Original contact (from Vayne CSV)
    original_first_name = Column(String)
    original_last_name = Column(String)

    # Decision maker (from Anymailfinder → {{firstName}} in Instantly)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String)
    email_status = Column(String)  # valid | risky | not_found | blacklisted

    # Company context
    company_name = Column(String)
    company_domain = Column(String)
    job_title = Column(String)
    industry = Column(String)
    linkedin_url = Column(Text)

    # AI enrichment
    company_summary = Column(Text)
    niche_pain_points = Column(Text)
    email_sequences = Column(JSON)  # 3 sequences × A/B

    # Pipeline state
    stage = Column(String, default="pending")  # pending|validated|researched|generated|deployed|skipped|error
    error_message = Column(Text)
    stage_updated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    batch = relationship("Batch", back_populates="leads")

    __table_args__ = (
        Index("idx_leads_stage", "stage", "batch_id"),
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("profiles.id"))
    batch_id = Column(Integer, ForeignKey("batches.id"))
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    delivered = Column(Boolean, default=False)
    response_status = Column(Integer)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("idx_webhook_pending", "delivered", "user_id"),
    )
