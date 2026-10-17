from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Investigation, InvestigationMember, User


def write_audit(
    db: Session,
    *,
    actor_id: str | None,
    action: str,
    investigation_id: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            investigation_id=investigation_id,
            action=action,
            details=details or {},
        )
    )


def get_investigation_for_user(db: Session, investigation_id: str, user: User) -> Investigation:
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")
    if user.role == "admin":
        return inv
    member = db.scalar(
        select(InvestigationMember).where(
            InvestigationMember.investigation_id == investigation_id,
            InvestigationMember.user_id == user.id,
        )
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this investigation")
    return inv
