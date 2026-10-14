from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")
    if len(pw) > 72:
        raise ValueError("Password must be at most 72 bytes")
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: int | str) -> tuple[str, int]:
    """Returns (token, expires_in_seconds)."""
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {"sub": str(subject), "iat": now, "exp": now + expires_delta}
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
