
"""IMAP integration for payment verification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import email
from email import policy
from email.message import Message
from email.utils import parsedate_to_datetime
import imaplib
import re

from .config import AppConfig
from .exceptions import GmailError
from .utils import utcnow


INCOMING_SUBJECT_RE = re.compile(r"you received ₹.* in your famx account", re.IGNORECASE)
INCOMING_BODY_RE = re.compile(r"you have successfully received", re.IGNORECASE)
OUTGOING_SUBJECT_RE = re.compile(r"your payment of ₹.* is successful", re.IGNORECASE)
OUTGOING_BODY_RE = re.compile(r"you have successfully paid", re.IGNORECASE)
# NOTE: the purpose prefix is configurable (AppConfig.purpose_prefix), so the
# matching pattern is built per-instance in GmailService._purpose_pattern()
# instead of being hardcoded here.
AMOUNT_RE = re.compile(r"₹\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")


@dataclass(slots=True)
class GmailMessage:
    """A simplified email message used during verification."""

    message_id: str
    subject: str
    body: str
    timestamp: datetime
    purpose: str | None
    amount: Decimal | None

    @property
    def is_incoming_payment(self) -> bool:
        """Return whether the email appears to be an incoming payment message."""

        subject = self.subject.strip()
        body = self.body.strip()

        if OUTGOING_SUBJECT_RE.search(subject) or OUTGOING_BODY_RE.search(body):
            return False
        if not INCOMING_SUBJECT_RE.search(subject):
            return False
        if not INCOMING_BODY_RE.search(body):
            return False
        return self.purpose is not None


class GmailService:
    """A lightweight wrapper around Gmail over IMAP."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        prefix = re.escape((config.purpose_prefix or "PS").upper())
        self._purpose_re = re.compile(rf"\b{prefix}-[A-Z0-9]{{8}}-[A-Z0-9]{{6}}\b")

    def _connect(self) -> imaplib.IMAP4_SSL:
        try:
            client = imaplib.IMAP4_SSL(self._config.imap_host, self._config.imap_port)
        except Exception as exc:  # noqa: BLE001
            raise GmailError(
                f"Unable to connect to IMAP server {self._config.imap_host}:{self._config.imap_port}."
            ) from exc

        try:
            status, _ = client.login(self._config.imap_username, self._config.imap_app_password)
        except imaplib.IMAP4.error as exc:
            raise GmailError(
                "Unable to authenticate to Gmail IMAP. Use your Google Account email address and an app password from myaccount.google.com/apppasswords."
            ) from exc

        if status != "OK":
            raise GmailError("IMAP login failed.")
        return client

    def _decode_bytes(self, value: bytes | None) -> str:
        if not value:
            return ""
        for encoding in ("utf-8", "latin-1"):
            try:
                return value.decode(encoding, errors="replace")
            except Exception:  # noqa: BLE001
                continue
        return value.decode("utf-8", errors="replace")

    def _extract_text_from_message(self, message: Message) -> str:
        if message.is_multipart():
            collected: list[str] = []
            for part in message.walk():
                content_disposition = part.get_content_disposition()
                content_type = part.get_content_type()
                if content_disposition == "attachment":
                    continue
                if content_type.startswith("text/"):
                    try:
                        text = part.get_content()
                    except Exception:  # noqa: BLE001
                        payload = part.get_payload(decode=True)
                        text = self._decode_bytes(payload)
                    if text:
                        collected.append(str(text))
            return "\\n".join(collected)

        try:
            content = message.get_content()
        except Exception:  # noqa: BLE001
            payload = message.get_payload(decode=True)
            return self._decode_bytes(payload)
        return str(content) if content is not None else ""

    def _parse_amount(self, text: str) -> Decimal | None:
        match = AMOUNT_RE.search(text)
        if not match:
            return None
        normalized = match.group(1).replace(",", "")
        try:
            return Decimal(normalized).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return None

    def _parse_timestamp(self, message: Message) -> datetime:
        date_header = message.get("Date")
        if date_header:
            try:
                timestamp = parsedate_to_datetime(date_header)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                return timestamp.astimezone(timezone.utc)
            except Exception:  # noqa: BLE001
                pass
        return utcnow()

    def _parse_message(self, raw: bytes, message_id: str) -> GmailMessage:
        message = email.message_from_bytes(raw, policy=policy.default)
        subject = str(message.get("Subject", ""))
        body = self._extract_text_from_message(message)
        timestamp = self._parse_timestamp(message)
        combined_text = f"{subject}\\n{body}"
        purpose_match = self._purpose_re.search(combined_text)
        purpose = purpose_match.group(0) if purpose_match else None
        amount = self._parse_amount(combined_text)
        return GmailMessage(
            message_id=message_id,
            subject=subject,
            body=body,
            timestamp=timestamp,
            purpose=purpose,
            amount=amount,
        )

    def _fetch_mailbox_messages(self, *, lookback_hours: int, max_results: int) -> list[GmailMessage]:
        cutoff = utcnow() - timedelta(hours=lookback_hours)
        since_date = cutoff.astimezone(timezone.utc).date()
        search_date = since_date.strftime("%d-%b-%Y")

        client = self._connect()
        try:
            try:
                status, _ = client.select(self._config.imap_mailbox)
            except imaplib.IMAP4.error as exc:
                raise GmailError(f"Unable to select IMAP mailbox '{self._config.imap_mailbox}'.") from exc
            if status != "OK":
                raise GmailError(f"Unable to select IMAP mailbox '{self._config.imap_mailbox}'.")

            try:
                status, data = client.search(None, "FROM", self._config.imap_sender_filter, "SINCE", search_date)
            except imaplib.IMAP4.error as exc:
                raise GmailError("Unable to query Gmail IMAP.") from exc
            if status != "OK":
                raise GmailError("Unable to query Gmail IMAP.")

            message_ids = data[0].split() if data and data[0] else []
            parsed: list[GmailMessage] = []
            for message_id_bytes in message_ids:
                message_id = message_id_bytes.decode("ascii", errors="ignore")
                try:
                    status, fetched = client.fetch(message_id_bytes, "(RFC822)")
                except imaplib.IMAP4.error:
                    continue
                if status != "OK":
                    continue
                raw_message = None
                for part in fetched:
                    if isinstance(part, tuple) and len(part) >= 2:
                        raw_message = part[1]
                        break
                if not raw_message:
                    continue
                try:
                    parsed_message = self._parse_message(raw_message, message_id)
                except Exception:  # noqa: BLE001
                    continue
                parsed.append(parsed_message)

            parsed.sort(key=lambda item: item.timestamp, reverse=True)
            return parsed[:max_results]
        finally:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass

    def search_incoming_payments(self, *, lookback_hours: int, max_results: int = 25) -> list[GmailMessage]:
        """Search Gmail for recent incoming payment emails via IMAP."""

        return self._fetch_mailbox_messages(lookback_hours=lookback_hours, max_results=max_results)

    def find_matching_incoming_payment(
        self,
        *,
        lookback_hours: int,
        order_created_at: datetime,
        expected_purpose: str,
        expected_amount: Decimal,
    ) -> GmailMessage | None:
        """Find the first valid incoming payment email for the supplied order.

        Primary match: purpose note + amount (most reliable, used first).
        Fallback match: some UPI apps strip the payment note/remarks field
        before it reaches FamApp, so if an email has NO purpose note at all
        (never one meant for a different order), fall back to matching by
        amount alone within a tight 10-minute window right after the order
        was created.
        """

        cutoff = utcnow() - timedelta(hours=lookback_hours)
        order_created_at = order_created_at.astimezone(timezone.utc)
        fallback_cutoff = order_created_at + timedelta(minutes=10)

        messages = self.search_incoming_payments(lookback_hours=lookback_hours)

        # Pass 1: strict purpose + amount match (safest).
        for message in messages:
            if message.timestamp < cutoff or message.timestamp < order_created_at:
                continue
            if not message.is_incoming_payment:
                continue
            if message.purpose != expected_purpose:
                continue
            if message.amount != expected_amount:
                continue
            return message

        # Pass 2: fallback for emails with no purpose note at all.
        for message in messages:
            if message.timestamp < order_created_at or message.timestamp > fallback_cutoff:
                continue
            if message.purpose:  # has a note -> meant for a different order, skip
                continue
            subject = message.subject.strip()
            body = message.body.strip()
            if OUTGOING_SUBJECT_RE.search(subject) or OUTGOING_BODY_RE.search(body):
                continue
            if not INCOMING_SUBJECT_RE.search(subject) or not INCOMING_BODY_RE.search(body):
                continue
            if message.amount != expected_amount:
                continue
            return message

        return None
