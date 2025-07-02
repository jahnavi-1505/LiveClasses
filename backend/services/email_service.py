import os
from typing import List
from email.message import EmailMessage
import aiosmtplib

# ← Fix import: go up from services/ into utils/
from ..utils.ics_utils import build_placeholder_ics, build_meeting_ics

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_FROM = os.getenv("EMAIL_FROM")

async def send_email_with_ics(
    to_emails: List[str],
    subject: str,
    body: str,
    ics_content: str,
    ics_filename: str = "invite.ics"
) -> None:
    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(to_emails)
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(
        ics_content.encode("utf-8"),
        maintype="text",
        subtype="calendar",
        filename=ics_filename,
        params={"method": "REQUEST", "charset": "UTF-8"}
    )
    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASS,
        start_tls=True
    )
