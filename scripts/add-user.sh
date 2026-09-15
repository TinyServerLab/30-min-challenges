#!/usr/bin/env bash
# Add (or reset the password of) a user from the Pi shell — handy if the admin locks themselves out.
#   ./scripts/add-user.sh you@example.com "Your Name" 'password' [--admin]
set -euo pipefail
EMAIL="${1:?email}"; NAME="${2:?name}"; PASS="${3:?password}"; ADMIN="${4:-}"
cd "$(dirname "$0")/.."
docker compose exec -T app python - "$EMAIL" "$NAME" "$PASS" "$ADMIN" <<'PY'
import sys
from sqlalchemy import select
from app.database import SessionLocal
from app.models import User
from app.auth import hash_password
email, name, pw, admin = sys.argv[1].lower(), sys.argv[2], sys.argv[3], sys.argv[4] == "--admin"
with SessionLocal() as db:
    u = db.scalar(select(User).where(User.email == email))
    if u:
        u.password_hash = hash_password(pw); u.name = name; u.is_active = True
        if admin: u.is_admin = True
        print(f"updated {email}")
    else:
        db.add(User(email=email, name=name, password_hash=hash_password(pw), is_admin=admin)); print(f"created {email}")
    db.commit()
PY
