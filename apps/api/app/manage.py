"""Local administrator provisioning requires shell access; no self-grant API."""

import sys
from .config import settings
from .db import Session, Account

if __name__ == "__main__":
    if settings().app_env not in ("local", "test"):
        raise SystemExit("Use deployment identity administrator in production")
    if len(sys.argv) != 3 or sys.argv[1] != "grant-admin":
        raise SystemExit("Usage: python -m app.manage grant-admin USERNAME")
    with Session.begin() as db:
        account = db.get(Account, sys.argv[2].lower())
        if not account:
            raise SystemExit("Register the account first")
        account.is_admin = True
    print("Administrator role saved")
