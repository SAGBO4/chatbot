import smtplib
import logging
import asyncio
from email.message import EmailMessage
from typing import Optional, Callable
from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def _send_smtp_sync(msg: EmailMessage) -> bool:
        """Synchronous SMTP sender run in an executor thread."""
        try:
            if not settings.SMTP_HOST or settings.SMTP_HOST == "smtp.example.com":
                logger.info("SMTP sending simulated (host not configured): %s", msg["Subject"])
                return True

            # Port 465 is implicit-TLS/SMTPS (Gmail SSL, iCloud, many corporate
            # hosts): it expects a TLS handshake from the very first byte and
            # rejects a plaintext EHLO, so it needs SMTP_SSL rather than
            # SMTP + starttls() (which only works with STARTTLS-style port 587).
            smtp_cls = smtplib.SMTP_SSL if settings.SMTP_PORT == 465 else smtplib.SMTP
            with smtp_cls(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10.0) as server:
                if settings.SMTP_USE_TLS and settings.SMTP_PORT != 465:
                    server.starttls()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            logger.info("Email sent successfully: %s to %s", msg["Subject"], msg["To"])
            return True
        except (smtplib.SMTPException, OSError) as exc:
            logger.error("Failed to send SMTP email: %s", exc)
            return False
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

        if not custom_sender and not settings.is_email_configured():
            logger.debug("Email dispatch bypassed (email is not fully configured).")
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
    ) -> bool:
        handle = user_handle or f"User_{user_id}"
        subject = f"[Ticket #{ticket_id}] Nouvelle demande de support de @{handle}"
        body = (
            f"Bonjour Équipe Support,\n\n"
            f"Un nouveau ticket d'assistance a été ouvert sur Telegram :\n\n"
            f"• Numéro de Ticket : #{ticket_id}\n"
            f"• Utilisateur : @{handle} (ID: {user_id})\n\n"
            f"❓ Question posée :\n{question}\n\n"
            f"🤖 Réponse automatique du bot :\n{automated_answer or 'Aucune'}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 Pour résoudre ce ticket, répondez directement à cet email avec votre solution.\n"
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
    ) -> bool:
        subject = f"[Ticket #{ticket_id}] Résolu via {resolution_channel}"
        body = (
            f"Bonjour Équipe Support,\n\n"
            f"Le Ticket #{ticket_id} vient d'être résolu sur le canal {resolution_channel}.\n\n"
            f"• Résolu par : {resolved_by or 'Non spécifié'}\n"
            f"• Canal : {resolution_channel}\n\n"
            f"📝 Solution apportée :\n{solution}\n\n"
            f"La solution a été automatiquement intégrée dans la base de connaissances.\n"
        )
        return await cls.send_email_async(
            subject=subject,
            body=body,
            custom_sender=custom_sender,
        )
