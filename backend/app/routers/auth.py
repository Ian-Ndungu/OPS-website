"""Minimal auth so the project runs standalone. When merging into the real OPS
app, delete this router and make `security.current_user` use your own auth."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.core import Role, User
from ..security import require_roles
from ..security import create_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    gamer_tag: str = Field(min_length=2, max_length=64)


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email already registered")
    u = User(email=body.email.lower(), hashed_password=hash_password(body.password), gamer_tag=body.gamer_tag, account_status="pending")
    db.add(u)
    db.commit()
    return {"status": "pending", "message": "Account created. An admin must approve your account before you can log in."}


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == form.username.lower()))
    if not u or not verify_password(form.password, u.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    if u.account_status != "active":
        raise HTTPException(403, "Your account is pending admin approval." if u.account_status == "pending" else "Your account has not been approved.")
    return {"access_token": create_token(u.id), "token_type": "bearer"}


@router.get("/me")
def me(u: User = Depends(current_user)):
    return {"id": u.id, "email": u.email, "gamer_tag": u.gamer_tag, "role": u.role,
            "is_verified_member": u.is_verified_member, "game_division": u.game_division}


@router.get("/admin/accounts")
def pending_accounts(_: User = Depends(require_roles(Role.clan_verifier)), db: Session = Depends(get_db)):
    return [{"id": u.id, "email": u.email, "gamer_tag": u.gamer_tag, "created_at": u.created_at}
            for u in db.scalars(select(User).where(User.account_status == "pending").order_by(User.created_at)).all()]


class AccountReview(BaseModel):
    approved: bool


@router.post("/admin/accounts/{user_id}/review")
def review_account(user_id: int, body: AccountReview,
                   _: User = Depends(require_roles(Role.clan_verifier)), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not user:
        raise HTTPException(404, "Account not found")
    if user.account_status != "pending":
        raise HTTPException(409, "Account has already been reviewed")
    user.account_status = "active" if body.approved else "rejected"
    db.commit()
    return {"id": user.id, "status": user.account_status}
