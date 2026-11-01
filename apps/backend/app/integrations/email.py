"""
SMTP email client.
Points to MailHog (localhost:1025) in dev; swap SMTP_* env vars for SendGrid in prod.
"""

import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.core.config import settings


async def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: str = "",
) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # TLS is configurable rather than hardcoded off (security/AUDIT.md SAHA-027).
    # The dev sink (Mailpit on loopback) speaks plaintext; any remote mail server
    # carries credentials and message bodies, and the boot guard refuses to start
    # an internet-facing deployment pointed at one without TLS.
    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME or None,
        password=settings.SMTP_PASSWORD or None,
        start_tls=settings.SMTP_USE_TLS,
    )


async def ping() -> bool:
    try:
        smtp = aiosmtplib.SMTP(hostname=settings.SMTP_HOST, port=settings.SMTP_PORT)
        await smtp.connect()
        await smtp.quit()
        return True
    except Exception:
        return False
