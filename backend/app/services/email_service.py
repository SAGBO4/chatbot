import smtplib
import logging
import asyncio
from email.message import EmailMessage
from typing import Optional, Callable
from app.config import settings
from app.i18n import DEFAULT_LANGUAGE, t

logger = logging.getLogger(__name__)


class EmailService:
    """Support notification emails over SMTP (sent from a thread so the event loop is never blocked)."""

    @staticmethod
    def _send_smtp_sync(msg: EmailMessage) -> bool:
        """Synchronous SMTP sender run in an executor thread."""
        try:
            if not settings.SMTP_HOST or settings.SMTP_HOST == "smtp.example.com":
                logger.info("SMTP sending simulated (host not configured): %s", msg["Subject"])
                return True

            # Port 465 is implicit TLS: it expects the handshake from the first byte, so it needs
            # SMTP_SSL; SMTP + starttls() only works on STARTTLS ports such as 587.
            smtp_cls = smtplib.SMTP_SSL if settings.SMTP_PORT == 465 else smtplib.SMTP
            with smtp_cls(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10.0) as server:
                if settings.SMTP_USE_TLS and settings.SMTP_PORT != 465:
                    server.starttls()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            logger.info("Email sent successfully: %s to %s", msg["Subject"], msg["To"])
            return True
        except Exception as exc:
            logger.error("Failed to send SMTP email: %s", exc)
            return False

    @classmethod
    async def send_email_async(
        cls,
        subject: str,
        body: str,
        to_email: Optional[str] = None,
        custom_sender: Optional[Callable[[EmailMessage], bool]] = None,
    ) -> bool:
        """Asynchronously dispatches an email message without blocking the caller."""
        if not settings.EMAIL_ENABLED:
            logger.debug("Email dispatch bypassed (EMAIL_ENABLED=False).")
            return True

        recipient = to_email or settings.SUPPORT_EMAIL_RECIPIENT
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = recipient
        msg.set_content(body)

        sender_fn = custom_sender or cls._send_smtp_sync
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, sender_fn, msg)

    @classmethod
    async def send_ticket_created_notification(
        cls,
        ticket_id: int,
        user_handle: Optional[str],
        user_id: int,
        question: str,
        automated_answer: Optional[str] = None,
        custom_sender: Optional[Callable[[EmailMessage], bool]] = None,
        lang: str = DEFAULT_LANGUAGE,
    ) -> bool:
        """Tell the support team a ticket was opened, in `lang`; replying to that email resolves it."""
        handle = user_handle or f"User_{user_id}"
        subject = t("email_ticket_created_subject", lang, ticket_id=ticket_id, handle=handle)
        body = t(
            "email_ticket_created_body", lang,
            ticket_id=ticket_id, handle=handle, user_id=user_id, question=question,
            answer=automated_answer or t("email_none", lang),
        )
        return await cls.send_email_async(
            subject=subject,
            body=body,
            custom_sender=custom_sender,
        )

    @classmethod
    async def send_ticket_resolved_notification(
        cls,
        ticket_id: int,
        resolved_by: Optional[str],
        resolution_channel: str,
        solution: str,
        custom_sender: Optional[Callable[[EmailMessage], bool]] = None,
        lang: str = DEFAULT_LANGUAGE,
    ) -> bool:
        """Tell the support team a ticket was resolved, and on which channel, in `lang`."""
        subject = t("email_ticket_resolved_subject", lang, ticket_id=ticket_id, channel=resolution_channel)
        body = t(
            "email_ticket_resolved_body", lang,
            ticket_id=ticket_id, channel=resolution_channel,
            resolved_by=resolved_by or t("email_unspecified", lang), solution=solution,
        )
        return await cls.send_email_async(
            subject=subject,
            body=body,
            custom_sender=custom_sender,
        )
