"""
Encryption utilities for user secrets (API keys, OAuth tokens).

Uses Fernet (AES-128-CBC with HMAC-SHA256) from the cryptography library.
Generate a key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import logging
from cryptography.fernet import Fernet, InvalidToken

from config import settings

log = logging.getLogger("security")

_fernet = None


def _get_fernet() -> Fernet:
    """Lazy-init Fernet cipher from ENCRYPTION_KEY."""
    global _fernet
    if _fernet is None:
        key = settings.ENCRYPTION_KEY
        if not key:
            log.warning(
                "ENCRYPTION_KEY not set — secrets stored in PLAIN TEXT. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
            return None
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a string. Returns encrypted string (base64). Falls back to plaintext if no key."""
    f = _get_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a string. Falls back to returning as-is if no key or decryption fails."""
    f = _get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception) as e:
        log.warning("Decryption failed (key mismatch or plain text?): %s", e)
        return ciphertext
