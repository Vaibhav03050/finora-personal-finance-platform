from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, func, select

from app.auth import require_admin
from app.database import get_session
from app.models import AuditLog, Transaction, User
from app.schemas import ok

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/overview")
def overview(admin: User = Depends(require_admin), session: Session = Depends(get_session)):
    user_count = session.exec(select(func.count()).select_from(User)).one()
    txn_count = session.exec(select(func.count()).select_from(Transaction)).one()
    beginner_count = session.exec(select(func.count()).select_from(User).where(User.is_beginner == True)).one()
    return ok({
        "total_users": user_count, "total_transactions": txn_count,
        "beginner_mode_users": beginner_count,
    })


@router.get("/audit-logs")
def audit_logs(
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)

    all_logs = session.exec(query.order_by(AuditLog.created_at.desc())).all()
    total = len(all_logs)
    start = (page - 1) * page_size
    page_logs = all_logs[start:start + page_size]

    return ok(
        [
            {"id": l.id, "user_id": l.user_id, "action": l.action, "detail": l.detail, "created_at": l.created_at.isoformat()}
            for l in page_logs
        ],
        meta={"page": page, "page_size": page_size, "total": total},
    )


@router.get("/health")
def system_health():
    return ok({"status": "healthy"})
