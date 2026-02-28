import argparse
import os
import sys

from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app
from extensions import db
from models import User, UserAuth


def build_unique_username(base: str) -> str:
    candidate = (base or "admin").strip().lower()
    suffix = 1
    while User.query.filter_by(username=candidate).first():
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


def upsert_admin(email: str, password: str, username: str | None, full_name: str | None):
    email = (email or "").strip().lower()
    if not email or not password:
        raise ValueError("email and password are required")

    auth = UserAuth.query.filter_by(email=email).first()
    if auth:
        user = auth.user
        user.role = "admin"
        if full_name:
            user.full_name = full_name
        if username and user.username != username:
            if User.query.filter(User.username == username, User.id != user.id).first():
                raise ValueError("username already exists")
            user.username = username
        auth.password_hash = generate_password_hash(password)
        db.session.commit()
        return user, False

    base_username = username or (email.split("@")[0] if "@" in email else "admin")
    final_username = build_unique_username(base_username)

    user = User(
        username=final_username,
        full_name=full_name,
        role="admin",
    )
    db.session.add(user)
    db.session.flush()

    auth = UserAuth(
        user_id=user.id,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(auth)
    db.session.commit()
    return user, True


def main():
    parser = argparse.ArgumentParser(description="Create or update an admin account")
    parser.add_argument("--email", required=True, help="Admin login email")
    parser.add_argument("--password", required=True, help="Admin login password")
    parser.add_argument("--username", help="Admin username (optional)")
    parser.add_argument("--full-name", dest="full_name", help="Admin full name (optional)")
    args = parser.parse_args()

    with app.app_context():
        user, created = upsert_admin(args.email, args.password, args.username, args.full_name)
        action = "Created" if created else "Updated"
        print(f"{action} admin user_id={user.id}, username={user.username}, email={args.email}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
