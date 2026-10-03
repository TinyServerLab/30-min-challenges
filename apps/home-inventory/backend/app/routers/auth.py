from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..schemas import LoginIn, PasswordChange, ProfileUpdate, UserOut
from ..security import (audit, client_ip, create_session, destroy_session, get_current_user,
                        hash_password, throttle, validate_password_strength, verify_password)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ident = body.login.strip().lower()
    keys = (f"ip:{client_ip(request)}", f"id:{ident}")
    if throttle.blocked(*keys):
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")
    user = db.scalar(select(User).where(or_(func.lower(User.email) == ident,
                                            func.lower(User.username) == ident)))
    ok = verify_password(body.password, user.password_hash if user else None)
    if not ok or not user or not user.is_active:
        throttle.fail(*keys)
        audit(db, user.id if user else None, "login.failed", detail_login=ident, ip=client_ip(request))
        db.commit()
        raise HTTPException(401, "Invalid credentials")
    throttle.reset(*keys)
    user.last_login_at = datetime.now(timezone.utc)
    create_session(db, user, request, response)
    audit(db, user.id, "login.success", ip=client_ip(request))
    db.commit()
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    destroy_session(db, request, response)
    db.commit()
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(user, k, v)
    db.merge(user)
    db.commit()
    return user


@router.post("/change-password", status_code=204)
def change_password(body: PasswordChange, request: Request, response: Response,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    validate_password_strength(body.new_password)
    u = db.get(User, user.id)
    u.password_hash = hash_password(body.new_password)
    # sign out every other session, keep this one fresh
    from ..models import UserSession
    from sqlalchemy import delete
    db.execute(delete(UserSession).where(UserSession.user_id == u.id))
    create_session(db, u, request, response)
    audit(db, u.id, "password.change")
    db.commit()
    response.status_code = 204
    return response
