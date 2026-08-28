"""Public payment manager exposed by the SDK."""

from __future__ import annotations

from datetime import timedelta, timezone
from decimal import Decimal
from typing import Any

from .config import AppConfig
from .database import MongoRepository
from .exceptions import OrderNotFoundError, OrderStateError, VerificationError
from .gmail import GmailService
from .models import Order, VerificationResult
from .purpose import generate_purpose
from .qr import build_upi_uri, generate_branded_qr
from .utils import generate_order_id, parse_amount, utcnow


class PaymentManager:
    """A lightweight payment verification SDK for FamApp-style flows."""

    def __init__(self) -> None:
        self._config = AppConfig.from_env()
        self._repository = MongoRepository(self._config)
        self._gmail = GmailService(self._config)

    def create(self, *, user_id: int, amount: float | int | str | Decimal) -> Order:
        """Create and persist a new pending payment order."""

        if not isinstance(user_id, int) or user_id <= 0:
            raise VerificationError("user_id must be a positive integer.")

        amount_decimal = parse_amount(amount)
        created_at = utcnow()
        expires_at = created_at + timedelta(minutes=self._config.order_expiry_minutes)
        order_id = generate_order_id()
        purpose = generate_purpose(self._config.purpose_prefix)
        upi_uri = build_upi_uri(
            upi_id=self._config.default_upi_id,
            payee_name=self._config.default_payee_name,
            amount=amount_decimal,
            purpose=purpose,
        )
        qr_image = generate_branded_qr(
            brand_name=self._config.brand_name,
            payee_name=self._config.default_payee_name,
            amount=amount_decimal,
            upi_uri=upi_uri,
            purpose=purpose,
            upi_id=self._config.default_upi_id,
        )

        order = Order(
            id=order_id,
            user_id=user_id,
            amount=amount_decimal,
            purpose=purpose,
            status="pending",
            qr_image=qr_image,
            upi_uri=upi_uri,
            payee_name=self._config.default_payee_name,
            created_at=created_at,
            expires_at=expires_at,
        )
        self._repository.save_order(order)
        return order

    def verify(self, order_id: str) -> dict[str, Any]:
        """Verify a pending order using IMAP and purpose matching."""

        order = self._repository.get_order(order_id)
        if order.status == "cancelled":
            raise OrderStateError("Cancelled orders cannot be verified.")
        if order.status == "verified":
            return VerificationResult(
                order_id=order.id,
                verified=True,
                status="verified",
                message="Order is already verified.",
            ).to_dict()

        now = utcnow()
        if now >= order.expires_at:
            expired_order = self._repository.update_order_status(order.id, "expired")
            return VerificationResult(
                order_id=expired_order.id,
                verified=False,
                status="expired",
                message="Order has expired.",
            ).to_dict()

        message = self._gmail.find_matching_incoming_payment(
            lookback_hours=self._config.gmail_lookback_hours,
            order_created_at=order.created_at,
            expected_purpose=order.purpose,
            expected_amount=order.amount,
        )

        if message is None:
            return VerificationResult(
                order_id=order.id,
                verified=False,
                status="pending",
                message="No matching payment email was found.",
            ).to_dict()

        if self._repository.message_already_processed(message.message_id):
            return VerificationResult(
                order_id=order.id,
                verified=False,
                status="pending",
                message="Matching email message was already processed.",
                gmail_message_id=message.message_id,
                purpose=message.purpose,
                amount=str(order.amount),
            ).to_dict()

        updated_order = self._repository.update_order_status(order.id, "verified")
        self._repository.save_verification_log(
            order_id=updated_order.id,
            gmail_message_id=message.message_id,
            purpose=updated_order.purpose,
            gmail_message_timestamp=message.timestamp,
        )

        return VerificationResult(
            order_id=updated_order.id,
            verified=True,
            status="verified",
            message="Payment verified successfully.",
            gmail_message_id=message.message_id,
            purpose=updated_order.purpose,
            verified_at=utcnow(),
        ).to_dict()

    def status(self, order_id: str) -> str:
        """Return the current order status."""

        order = self._repository.get_order(order_id)
        if order.status == "pending" and utcnow() >= order.expires_at:
            self._repository.update_order_status(order.id, "expired")
            return "expired"
        return order.status

    def cancel(self, order_id: str) -> Order:
        """Cancel a pending order."""

        order = self._repository.get_order(order_id)
        if order.status != "pending":
            raise OrderStateError("Only pending orders can be cancelled.")
        return self._repository.update_order_status(order.id, "cancelled")
