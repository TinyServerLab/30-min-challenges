"""
Seed (or add) a household user. There is no self-registration endpoint by
design — run this from the host whenever a new person needs a login:

    docker compose exec app python scripts/seed_admin.py \
        --email you@example.com --name "Sathya" --password 'a-strong-password'

Re-running with an existing email updates that user's name/password instead
of creating a duplicate.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        email = args.email.lower().strip()
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.full_name = args.name
            user.password_hash = hash_password(args.password)
            user.is_active = True
            action = "Updated"
        else:
            user = User(email=email, full_name=args.name, password_hash=hash_password(args.password))
            db.add(user)
            action = "Created"
        db.commit()
        print(f"{action} user {email} ({args.name})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
