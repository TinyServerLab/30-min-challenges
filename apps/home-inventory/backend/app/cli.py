"""Admin CLI (the "seed mechanism" — there is no public registration).

  docker compose exec app python -m app.cli create-user --email amma@example.com --name "Amma"
  docker compose exec app python -m app.cli create-user --email me@example.com --name Sathya --admin
  docker compose exec app python -m app.cli reset-password --email amma@example.com
  docker compose exec app python -m app.cli list-users
  docker compose exec app python -m app.cli migrate
  docker compose exec app python -m app.cli send-reminders
"""
import argparse
import getpass
import sys

from fastapi import HTTPException
from sqlalchemy import delete, func, select

from .db import SessionLocal
from .migrate import run_migrations
from .models import User, UserSession
from .security import hash_password, validate_password_strength


def _password(args) -> str:
    pw = args.password or getpass.getpass("Password: ")
    if not args.password and pw != getpass.getpass("Repeat:   "):
        sys.exit("Passwords do not match")
    try:
        validate_password_strength(pw)
    except HTTPException as e:
        sys.exit(e.detail)
    return pw


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-user")
    c.add_argument("--email", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--username")
    c.add_argument("--admin", action="store_true")
    c.add_argument("--password", help="omit to be prompted (recommended)")
    r = sub.add_parser("reset-password")
    r.add_argument("--email", required=True)
    r.add_argument("--password")
    sub.add_parser("list-users")
    sub.add_parser("migrate")
    sub.add_parser("send-reminders")
    args = p.parse_args()

    if args.cmd == "migrate":
        print("Applied:", run_migrations() or "nothing (up to date)")
        return
    if args.cmd == "send-reminders":
        from .reminders import run_reminders
        print(run_reminders())
        return

    run_migrations()
    with SessionLocal() as db:
        if args.cmd == "list-users":
            for u in db.scalars(select(User).order_by(User.id)):
                print(f"{u.id:>3}  {u.email:<35} {u.display_name:<20} {'admin' if u.is_admin else ''}"
                      f"{'' if u.is_active else ' (disabled)'}")
        elif args.cmd == "create-user":
            if db.scalar(select(User).where(func.lower(User.email) == args.email.lower())):
                sys.exit("A user with that email already exists")
            pw = _password(args)
            db.add(User(email=args.email.lower(), username=args.username, display_name=args.name,
                        password_hash=hash_password(pw), is_admin=args.admin))
            db.commit()
            print(f"Created {'admin ' if args.admin else ''}user {args.email}")
        elif args.cmd == "reset-password":
            u = db.scalar(select(User).where(func.lower(User.email) == args.email.lower()))
            if not u:
                sys.exit("No such user")
            u.password_hash = hash_password(_password(args))
            db.execute(delete(UserSession).where(UserSession.user_id == u.id))
            db.commit()
            print("Password reset; existing sessions signed out")


if __name__ == "__main__":
    main()
