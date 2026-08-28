"""Internal data models used by the payment SDK."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Literal

from .utils import decode_bytes, encode_bytes, ensure_utc

OrderStatus = Literal["pending", "verified", "expired", "cancelled"]


@dataclass(slots=True)
class Order:
    """A payment order returned to the consumer."""

    id: str
    user_id: int
    amount: Decimal
    purpose: str
    status: OrderStatus
    qr_image: bytes
    upi_uri: str
    payee_name: str
    created_at: datetime
    expires_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert the order into a JSON-serializable dictionary."""

        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": str(self.amount),
            "purpose": self.purpose,
            "status": self.status,
            "qr_image": encode_bytes(self.qr_image),
            "upi_uri": self.upi_uri,
            "payee_name": self.payee_name,
            "created_at": ensure_utc(self.created_at).isoformat(),
            "expires_at": ensure_utc(self.expires_at).isoformat(),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "Order":
        """Build an order from a MongoDB record."""

        return cls(
            id=str(record["id"]),
            user_id=int(record["user_id"]),
            amount=Decimal(str(record["amount"])),
            purpose=str(record["purpose"]),
            status=str(record["status"]),  # type: ignore[arg-type]
            qr_image=decode_bytes(record["qr_image"]),
            upi_uri=str(record["upi_uri"]),
            payee_name=str(record["payee_name"]),
            created_at=ensure_utc(record["created_at"]),
            expires_at=ensure_utc(record["expires_at"]),
        )

    def to_record(self) -> dict[str, Any]:
        """Convert the order into a MongoDB record."""

        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": str(self.amount),
            "purpose": self.purpose,
            "status": self.status,
            "qr_image": self.qr_image,
            "upi_uri": self.upi_uri,
            "payee_name": self.payee_name,
            "created_at": ensure_utc(self.created_at),
            "expires_at": ensure_utc(self.expires_at),
        }


@dataclass(slots=True)
class VerificationResult:
    """Result returned by payment verification."""

    order_id: str
    verified: bool
    status: str
    message: str
    gmail_message_id: str | None = None
    purpose: str | None = None
    amount: Decimal | None = None
    verified_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the result into a serializable dictionary."""

        return {
            "order_id": self.order_id,
            "verified": self.verified,
            "status": self.status,
            "message": self.message,
            "gmail_message_id": self.gmail_message_id,
            "purpose": self.purpose,
            "amount": str(self.amount) if self.amount is not None else None,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }
