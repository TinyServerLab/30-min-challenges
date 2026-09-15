from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import (
    admin_user,
    clear_session_cookie,
    create_token,
    current_user,
    hash_password,
    set_session_cookie,
    verify_password,
)
from ..database import get_db
from ..models import User

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=schemas.UserOut)
def login(body: schemas.LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        # same message either way: don't leak which emails exist
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled")
    set_session_cookie(response, create_token(user))
    return user


@router.post("/auth/logout", status_code=204)
def logout(response: Response):
    clear_session_cookie(response)


@router.get("/auth/me", response_model=schemas.UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.post("/auth/password", status_code=204)
def change_password(
    body: schemas.PasswordChange,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    db.commit()


# ---- admin: seeded users, no self-registration ----
@router.get("/users", response_model=list[schemas.UserOut])
def list_users(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post("/users", response_model=schemas.UserOut, status_code=201)
def create_user(body: schemas.UserCreate, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with that email already exists")
    user = User(email=email, name=body.name, password_hash=hash_password(body.password), is_admin=body.is_admin)
    db.add(user)
    db.commit()
    return user


@router.patch("/users/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int, body: schemas.UserUpdate, admin: User = Depends(admin_user), db: Session = Depends(get_db)
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin.id and (body.is_admin is False or body.is_active is False):
        raise HTTPException(400, "You can't demote or disable your own account")
    if body.name is not None:
        user.name = body.name
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    if body.is_admin is not None:
        user.is_admin = body.is_admin
    if body.is_active is not None:
        user.is_active = body.is_active
    db.commit()
    return user
