"""
Password hashing and session tokens.

Uses only the standard library. scrypt is memory-hard and available in
hashlib, so there is no dependency to keep patched for something this
security-sensitive, and no risk of the container shipping without it.
"""
import hashlib
import hmac
import os
import secrets
from typing import Optional

# Cost parameters. n is the work factor; 2**14 keeps a single verification
# around a tenth of a second on modest hardware, which is slow enough to make
# guessing expensive and fast enough not to be noticed at login.
_N = 2 ** 14
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16

MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    """Salted scrypt digest, stored as scheme$salt$key so it can be upgraded later."""
    salt = os.urandom(_SALT_BYTES)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return f"scrypt${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    """Constant-time comparison, and never raises on a malformed record."""
    if not stored:
        return False
    try:
        scheme, salt_hex, key_hex = stored.split("$", 2)
        if scheme != "scrypt":
            return False
        key = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=_N, r=_R, p=_P, dklen=_DKLEN,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(key.hex(), key_hex)


def new_token() -> str:
    """An opaque session token. Stored server-side, so it can be revoked."""
    return secrets.token_urlsafe(32)


def password_problem(password: str) -> Optional[str]:
    """Why a password is unacceptable, or None if it is fine."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return None
