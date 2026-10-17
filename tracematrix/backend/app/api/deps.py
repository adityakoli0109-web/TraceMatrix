from collections import defaultdict
from time import time

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Investigation, User
from app.security import get_current_user
from app.services.access import get_investigation_for_user

_attempts: dict[str, list[float]] = defaultdict(list)


def throttle_login(request: Request) -> None:
    settings = get_settings()
    key = f"{request.client.host if request.client else 'unknown'}"
    now = time()
    window = [t for t in _attempts[key] if now - t < settings.login_window_seconds]
    if len(window) >= settings.login_max_attempts:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")
    window.append(now)
    _attempts[key] = window


def investigation_access(
    investigation_id: str,
    db: Session,
    user: User = Depends(get_current_user),
) -> Investigation:
    return get_investigation_for_user(db, investigation_id, user)
