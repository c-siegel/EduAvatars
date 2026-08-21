"""
Bootstrap Admin Account

An idempotent startup step that creates or promotes an admin account from ADMIN_EMAIL/
ADMIN_PASSWORD (see core/config.py) — the way a self-hoster gets their first admin without
touching the database by hand. Run automatically by docker/backend-entrypoint.sh right after
migrations; for a non-Docker deploy, run it manually the same way.

What does it do?
- Neither ADMIN_EMAIL nor ADMIN_PASSWORD set: does nothing (most instances, most of the time).
- ADMIN_EMAIL doesn't match an existing account: creates one with that email/password, already
  an admin, flagged to change that password on first login.
- ADMIN_EMAIL matches an existing non-admin account: promotes it to admin. Never touches its
  password — only a brand-new account gets one from ADMIN_PASSWORD.
- ADMIN_EMAIL already belongs to an admin: does nothing.

Safe to run on every container start (and to leave the env vars set indefinitely) — none of the
above ever re-applies a change that's already in place.

How to use:
    python -m app.cli.bootstrap_admin
"""

import logging

from sqlmodel import Session, select

from app.core.config import settings
from app.db.session import engine
from app.models.user import User
from app.services.auth_service import register_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def bootstrap_admin() -> None:
    """Create-or-promote the ADMIN_EMAIL/ADMIN_PASSWORD account to admin, if both are set."""
    if not settings.admin_email or not settings.admin_password:
        logger.info("ADMIN_EMAIL/ADMIN_PASSWORD not set — skipping admin bootstrap.")
        return

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == settings.admin_email)).first()
        if user is None:
            user = register_user(session, name="Admin", email=settings.admin_email, password=settings.admin_password)
            user.is_admin = True
            user.must_change_password = True
            session.add(user)
            session.commit()
            logger.info("Created new admin account for %s.", settings.admin_email)
        elif not user.is_admin:
            user.is_admin = True
            session.add(user)
            session.commit()
            logger.info("Promoted existing account %s to admin.", settings.admin_email)
        else:
            logger.info("%s is already an admin — nothing to do.", settings.admin_email)


if __name__ == "__main__":
    bootstrap_admin()
