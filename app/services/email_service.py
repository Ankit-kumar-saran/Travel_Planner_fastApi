"""Sends the password reset email using Python's built-in smtplib."""
import smtplib
from email.message import EmailMessage

from app.config import settings


def send_reset_email(to_email: str, token: str) -> None:
    link = f"{settings.frontend_url}/reset-password.html?token={token}"

    # Development mode: no SMTP configured -> print the link in the server console
    if not settings.smtp_host:
        print(f"[DEV] Password reset link for {to_email}: {link}")
        return

    message = EmailMessage()
    message["Subject"] = "WanderSync password reset"
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message.set_content(
        "You asked to reset your WanderSync password.\n\n"
        f"Open this link (valid for 30 minutes):\n{link}\n\n"
        "If you did not ask for this, ignore this email."
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)
