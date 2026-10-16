"""Create staff accounts for first-time setup (no demo content, no fake data).

    python seed_admins.py                 # prompts for passwords
Staff roles: super_admin, finance_admin (x2 recommended for two-person payout approval),
clan_verifier, results_admin, content_admin.
"""
import getpass
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models.core import Role, User
from app.security import hash_password


def main():
    print("Create a staff account. Ctrl+C to stop.")
    with SessionLocal() as db:
        while True:
            email = input("Email: ").strip().lower()
            tag = input("Gamer tag: ").strip()
            role = input(f"Role {[r.value for r in Role if r != Role.member]}: ").strip()
            if role not in {r.value for r in Role}:
                print("Unknown role"); continue
            pw = getpass.getpass("Password (min 12 chars): ")
            if len(pw) < 12:
                print("Too short"); continue
            u = db.scalar(select(User).where(User.email == email))
            if u:
                u.role = role
            else:
                db.add(User(email=email, gamer_tag=tag, role=role, hashed_password=hash_password(pw)))
            db.commit()
            print("Saved.\n")
            if input("Another? [y/N] ").lower() != "y":
                break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
