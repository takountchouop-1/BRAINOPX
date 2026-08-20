import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL")


def send_password_reset_email(to_email: str, code: str) -> None:
    """Send a 6-digit password reset code to the given email address."""
    subject = "Your BRAINOPX Assistant password reset code"
    body = (
        f"Hello,\n\n"
        f"Your password reset code is: {code}\n\n"
        f"This code will expire in 15 minutes. If you did not request "
        f"this, you can safely ignore this email.\n\n"
        f"- BRAINOPX Configuration Assistant"
    )

    message = MIMEMultipart()
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_APP_PASSWORD)
        server.sendmail(SMTP_FROM_EMAIL, to_email, message.as_string())


def send_new_user_email(to_email: str, full_name: str, temporary_password: str) -> None:
    """
    Tell a newly created user their account and temporary password.

    Callers should treat this as best-effort: an admin creating a user
    is not blocked on SMTP being configured or reachable, since the
    temporary password is also returned directly in the API response.
    """
    subject = "Your BRAINOPX Assistant account"
    body = (
        f"Hello {full_name},\n\n"
        f"An account has been created for you on BRAINOPX Assistant.\n\n"
        f"Email: {to_email}\n"
        f"Temporary password: {temporary_password}\n\n"
        f"Please sign in and change this password as soon as possible.\n\n"
        f"- BRAINOPX Configuration Assistant"
    )

    message = MIMEMultipart()
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_APP_PASSWORD)
        server.sendmail(SMTP_FROM_EMAIL, to_email, message.as_string())