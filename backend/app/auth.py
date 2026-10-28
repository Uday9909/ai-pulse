import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from .config import PASSWORD_ROUNDS, SECRET_KEY, TOKEN_HOURS
from .db import get_db
from . import models

PBKDF2_PREFIX = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    """Salted PBKDF2-HMAC-SHA256. The demo password stays the same; only the stored form changes."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ROUNDS)
    return f"{PBKDF2_PREFIX}${PASSWORD_ROUNDS}${salt.hex()}${digest.hex()}"


def _verify_pbkdf2(password: str, stored: str) -> bool:
    algorithm, rounds, salt_hex, digest_hex = stored.split("$")
    if algorithm != PBKDF2_PREFIX:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def verify_password(password: str, hashed: str) -> bool:
    try:
        if hashed.startswith(f"{PBKDF2_PREFIX}$"):
            return _verify_pbkdf2(password, hashed)
        # Legacy rows: unsalted SHA-256. Still accepted, then upgraded on login.
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy, hashed)
    except (ValueError, TypeError, AttributeError):
        return False


def password_needs_rehash(hashed: str) -> bool:
    return not hashed.startswith(f"{PBKDF2_PREFIX}$")


def make_token(user_id: int, org_id: int | None = None) -> str:
    payload = {
        "sub": str(user_id),
        "org": org_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _decode(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        return jwt.decode(
            authorization[7:],
            SECRET_KEY,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")


def current_user(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> models.User:
    data = _decode(authorization)
    user = db.get(models.User, int(data["sub"]))
    if not user:
        raise HTTPException(401, "Unknown user")
    return user


def current_membership(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> models.Membership:
    """The membership for the organization selected after login."""
    data = _decode(authorization)
    if not data.get("org"):
        raise HTTPException(400, "Select an organization first")
    m = (
        db.query(models.Membership)
        .filter_by(user_id=int(data["sub"]), org_id=data["org"])
        .first()
    )
    if not m:
        raise HTTPException(403, "Not a member of this organization")
    return m
