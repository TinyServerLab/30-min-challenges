from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, UserSession
from ..schemas import PasswordReset, UserCreate, UserOut, UserUpdate
from ..security import audit, hash_password, require_admin, validate_password_strength

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    validate_password_strength(body.password)
    clash = db.scalar(select(User.id).where(or_(
        func.lower(User.email) == body.email.lower(),
        func.lower(User.username) == (body.username or "").lower())))
    if clash:
        raise HTTPException(409, "Email or username already in use")
    u = User(email=body.email.lower(), username=body.username, display_name=body.display_name,
             password_hash=hash_password(body.password), is_admin=body.is_admin)
    db.add(u)
    db.flush()
    audit(db, admin.id, "user.create", "user", u.id, email=u.email)
    db.commit()
    return u


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    if u.id == admin.id and (data.get("is_admin") is False or data.get("is_active") is False):
        raise HTTPException(400, "You cannot remove your own admin rights or deactivate yourself")
    for k, v in data.items():
        setattr(u, k, v or None if k == "username" else v)
    if data.get("is_active") is False:
        db.execute(delete(UserSession).where(UserSession.user_id == u.id))
    audit(db, admin.id, "user.update", "user", u.id, **{k: str(v) for k, v in data.items()})
    db.commit()
    return u


@router.post("/{user_id}/reset-password", status_code=204)
def reset_password(user_id: int, body: PasswordReset, admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    validate_password_strength(body.new_password)
    u.password_hash = hash_password(body.new_password)
    db.execute(delete(UserSession).where(UserSession.user_id == u.id))
    audit(db, admin.id, "user.reset_password", "user", u.id)
    db.commit()
