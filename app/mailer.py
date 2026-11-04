"""Email: every message is stored in the outbox; it is sent by SMTP when
SMTP_HOST is configured (free tiers of Brevo, Mailjet, Zoho etc. work)."""
import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from .config import settings
from .models import EmailOutbox


def send_email(db: Session, to: str, subject: str, body: str) -> EmailOutbox:
    msg = EmailOutbox(to=to, subject=subject, body=body)
    db.add(msg)
    db.flush()
    if settings.SMTP_HOST:
        try:
            m = EmailMessage()
            m["From"], m["To"], m["Subject"] = settings.MAIL_FROM, to, subject
            m.set_content(body)
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as s:
                s.starttls()
                if settings.SMTP_USER:
                    s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                s.send_message(m)
            msg.sent = True
        except Exception as e:  # keep it in the outbox for retry
            msg.error = str(e)[:500]
    return msg
