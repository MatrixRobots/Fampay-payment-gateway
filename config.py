
"""Configuration loading for the payment SDK."""

from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv

from .exceptions import ConfigurationError


def _parse_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer.") from exc
    if parsed <= 0:
        raise ConfigurationError(f"{name} must be greater than zero.")
    return parsed


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Runtime configuration resolved from environment variables."""

    mongodb_uri: str
    db_name: str
    default_upi_id: str
    default_payee_name: str = "Project Stack"
    purpose_prefix: str = "PS"
    brand_name: str = "Project Stack"
    order_expiry_minutes: int = 15
    gmail_lookback_hours: int = 12
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_username: str = ""
    imap_app_password: str = ""
    imap_mailbox: str = "INBOX"
    imap_sender_filter: str = "no-reply@famapp.in"

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load the SDK configuration from environment variables and .env files."""

        load_dotenv()

        mongodb_uri = os.getenv("MONGODB_URI", "").strip()
        db_name = os.getenv("DB_NAME", "").strip()
        default_upi_id = os.getenv("DEFAULT_UPI_ID", "").strip()

        if not mongodb_uri:
            raise ConfigurationError("MONGODB_URI is required.")
        if not db_name:
            raise ConfigurationError("DB_NAME is required.")
        if not default_upi_id:
            raise ConfigurationError("DEFAULT_UPI_ID is required.")

        default_payee_name = os.getenv("DEFAULT_PAYEE_NAME", "Project Stack").strip() or "Project Stack"
        purpose_prefix = os.getenv("PURPOSE_PREFIX", "PS").strip().upper() or "PS"
        brand_name = os.getenv("BRAND_NAME", "Project Stack").strip() or "Project Stack"

        order_expiry_minutes = _parse_int(os.getenv("ORDER_EXPIRY_MINUTES", "15"), "ORDER_EXPIRY_MINUTES")
        gmail_lookback_hours = _parse_int(os.getenv("GMAIL_LOOKBACK_HOURS", "12"), "GMAIL_LOOKBACK_HOURS")
        imap_port = _parse_int(os.getenv("IMAP_PORT", "993"), "IMAP_PORT")

        imap_host = os.getenv("IMAP_HOST", "imap.gmail.com").strip() or "imap.gmail.com"
        imap_username = os.getenv("IMAP_USERNAME", "").strip()
        imap_app_password = os.getenv("IMAP_APP_PASSWORD", "").strip()
        imap_mailbox = os.getenv("IMAP_MAILBOX", "INBOX").strip() or "INBOX"
        imap_sender_filter = os.getenv("IMAP_SENDER_FILTER", "no-reply@famapp.in").strip() or "no-reply@famapp.in"

        if not imap_username:
            raise ConfigurationError("IMAP_USERNAME is required.")
        if not imap_app_password:
            raise ConfigurationError("IMAP_APP_PASSWORD is required.")

        return cls(
            mongodb_uri=mongodb_uri,
            db_name=db_name,
            default_upi_id=default_upi_id,
            default_payee_name=default_payee_name,
            purpose_prefix=purpose_prefix,
            brand_name=brand_name,
            order_expiry_minutes=order_expiry_minutes,
            gmail_lookback_hours=gmail_lookback_hours,
            imap_host=imap_host,
            imap_port=imap_port,
            imap_username=imap_username,
            imap_app_password=imap_app_password,
            imap_mailbox=imap_mailbox,
            imap_sender_filter=imap_sender_filter,
        )
