"""Email utilities for server.

Provides a simple function to send email via Gmail using an app password.

Environment variables used:
- `GOOGLE_APP_EMAIL`: sender Gmail address (e.g. youraccount@gmail.com)
- `GOOGLE_APP_PASSWORD`: Gmail app password

This module avoids external dependencies and uses the stdlib `smtplib` and
`email.message.EmailMessage`.
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Iterable, Optional


class EmailSendError(Exception):
    """Raised when sending email fails due to configuration or SMTP errors."""


def send_via_gmail(
    subject: str,
    body: str,
    to_addrs: Optional[Iterable[str]] = None,
    from_addr: Optional[str] = None,
    cc: Optional[Iterable[str]] = None,
    bcc: Optional[Iterable[str]] = None,
) -> None:
    """Send an email using Gmail SMTP (SSL) and an app password.

    Reads `GOOGLE_APP_PASSWORD` and `GOOGLE_APP_EMAIL` from the environment.

    Args:
        subject: Email subject.
        body: Email body (plain text).
        to_addrs: Iterable of recipient email addresses.
        from_addr: Optional from address. If not provided, `GOOGLE_APP_EMAIL` is used.
        cc: Optional iterable of CC addresses.
        bcc: Optional iterable of BCC addresses.

    Raises:
        EmailSendError: If configuration is missing or SMTP fails.
    """
    password = os.getenv("GOOGLE_APP_PASSWORD")
    configured_email = os.getenv("GOOGLE_APP_EMAIL")

    # Normalize recipients
    to_list = list(to_addrs or [configured_email])
    cc_list = list(cc or [])
    bcc_list = list(bcc or [])

    if not to_list and not cc_list and not bcc_list:
        raise EmailSendError("no recipients provided")

    if not password:
        raise EmailSendError("environment variable GOOGLE_APP_PASSWORD is not set")


    if from_addr is None:
        if not configured_email:
            raise EmailSendError(
                "from_addr not provided and GOOGLE_APP_EMAIL environment variable is not set"
            )
        from_addr = configured_email

    # Build message
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    # Note: Bcc is not added to headers
    #msg.set_content(body)
    msg.add_alternative(body, subtype="html")

    all_recipients = to_list + cc_list + bcc_list

    smtp_host = "smtp.gmail.com"
    smtp_port = 465  # SSL

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as smtp:
            smtp.login(from_addr, password)
            smtp.send_message(msg, from_addr=from_addr, to_addrs=all_recipients)
    except Exception as exc:  # pragma: no cover - broad catch converts to EmailSendError
        raise EmailSendError(f"failed to send email: {exc}") from exc
