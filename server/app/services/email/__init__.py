"""Transactional email sender for auth flows.

Per docs/40-features/AUTH.md §3.3 — magic link delivery uses this module.
Digest delivery has a separate adapter at `app.services.digest.delivery`
for historical reasons.
"""

from app.services.email.sender import (
    EmailMessage,
    EmailSender,
    EmailSendError,
    LogEmailSender,
    ResendEmailSender,
    default_email_sender,
)

__all__ = [
    "EmailMessage",
    "EmailSendError",
    "EmailSender",
    "LogEmailSender",
    "ResendEmailSender",
    "default_email_sender",
]
