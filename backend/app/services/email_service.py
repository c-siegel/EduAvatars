"""
Sending Transactional Email

Sends the password-reset email. Deliberately uses the stdlib smtplib instead of an extra
dependency (e.g. a transactional-mail SDK) — fits an institutional hosting context (a
university/school IT department usually runs its own SMTP relay, so no third-party API key is
needed). If SMTP_HOST is empty (settings.smtp_configured is False), nothing is actually sent —
see password_reset_service.py.

How to use:
    from app.services.email_service import send_password_reset_email

    send_password_reset_email(user.email, reset_link)
"""

import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    """Send the password-reset email with the reset link to `to_email`."""
    message = EmailMessage()
    message["Subject"] = "EduAvatars — Passwort zurücksetzen"
    message["From"] = settings.smtp_from_address
    message["To"] = to_email
    message.set_content(
        "Hallo,\n\n"
        "für dein EduAvatars-Konto wurde ein Zurücksetzen des Passworts angefordert.\n"
        f"Falls du das warst, klicke auf folgenden Link (gültig für {settings.password_reset_token_expire_minutes} Minuten):\n\n"
        f"{reset_link}\n\n"
        "Falls du das nicht warst, kannst du diese E-Mail ignorieren — dein Passwort bleibt unverändert.\n"
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
