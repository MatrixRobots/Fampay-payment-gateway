"""Shared helper functions for the payment SDK."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import base64
import secrets
import string

from .exceptions import ConfigurationError


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_amount(value: float | int | str | Decimal) -> Decimal:
    """Parse a user-provided amount into a positive Decimal."""

    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ConfigurationError("amount must be a valid number.") from exc

    if amount <= 0:
        raise ConfigurationError("amount must be greater than zero.")
    return amount


def format_amount(amount: Decimal) -> str:
    """Format an amount for use in UPI URIs."""

    normalized = amount.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def encode_bytes(data: bytes) -> str:
    """Encode bytes as a base64 string."""

    return base64.b64encode(data).decode("ascii")


def decode_bytes(value: str | bytes) -> bytes:
    """Decode bytes from a base64 string or pass through raw bytes."""

    if isinstance(value, bytes):
        return value
    return base64.b64decode(value.encode("ascii"))


def generate_order_id() -> str:
    """Generate a compact human-readable order identifier."""

    return f"ORD-{utcnow().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"


def slugify_upper(value: str) -> str:
    """Return an uppercase token with non-alphanumeric characters removed."""

    cleaned = "".join(ch for ch in value.upper() if ch.isalnum())
    return cleaned or "PS"


def generate_secure_suffix(length: int = 6) -> str:
    """Generate an uppercase secure random suffix."""

    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
