from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_session
from app.models import AuditLog, User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, fail, ok

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register")
def register(payload: RegisterRequest, session: Session = Depends(get_session)):
    existing = session.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(email=payload.email, password_hash=hash_password(payload.password), name=payload.name)
    session.add(user)
    session.commit()
    session.refresh(user)
    session.add(AuditLog(user_id=user.id, action="register", detail=user.email))
    session.commit()

    token = create_access_token(subject=str(user.id), role=user.role.value)
    return ok(TokenResponse(
        access_token=token, user_id=user.id, name=user.name, email=user.email, is_beginner=user.is_beginner,
    ).model_dump())


@router.post("/login")
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(subject=str(user.id), role=user.role.value)
    session.add(AuditLog(user_id=user.id, action="login"))
    session.commit()
    return ok(TokenResponse(
        access_token=token, user_id=user.id, name=user.name, email=user.email, is_beginner=user.is_beginner,
    ).model_dump())


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return ok({
        "id": user.id, "email": user.email, "name": user.name,
        "role": user.role.value, "language": user.language, "is_beginner": user.is_beginner,
    })
