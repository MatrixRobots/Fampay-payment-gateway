"""MongoDB persistence for orders and verification logs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pymongo import MongoClient, ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from .config import AppConfig
from .exceptions import DatabaseError, OrderNotFoundError
from .models import Order, OrderStatus
from .utils import ensure_utc, utcnow


@dataclass(slots=True)
class VerificationLogRecord:
    """Persistent record written after a successful verification."""

    order_id: str
    gmail_message_id: str
    purpose: str
    verified_at: datetime
    gmail_message_timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "gmail_message_id": self.gmail_message_id,
            "purpose": self.purpose,
            "verified_at": self.verified_at,
            "gmail_message_timestamp": self.gmail_message_timestamp,
        }


class MongoRepository:
    """A small MongoDB repository focused on the orders collection."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client: MongoClient | None = None
        self._db = None
        self._indexes_ready = False

    @property
    def db(self):
        if self._db is None:
            self._connect()
        return self._db

    def _connect(self) -> None:
        try:
            self._client = MongoClient(
                self._config.mongodb_uri,
                tz_aware=True,
                serverSelectionTimeoutMS=5000,
            )
            self._db = self._client[self._config.db_name]
            self._ensure_indexes()
        except PyMongoError as exc:
            raise DatabaseError("Unable to connect to MongoDB.") from exc

    def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        try:
            self.orders.create_index("id", unique=True)
            self.verification_logs.create_index("gmail_message_id", unique=True)
            self.verification_logs.create_index([("order_id", 1), ("verified_at", -1)])
            self._indexes_ready = True
        except PyMongoError as exc:
            raise DatabaseError("Unable to create MongoDB indexes.") from exc

    @property
    def orders(self) -> Collection:
        return self.db["orders"]

    @property
    def verification_logs(self) -> Collection:
        return self.db["verification_logs"]

    def save_order(self, order: Order) -> None:
        try:
            self.orders.insert_one(order.to_record())
        except PyMongoError as exc:
            raise DatabaseError("Unable to save order.") from exc

    def get_order(self, order_id: str) -> Order:
        try:
            record = self.orders.find_one({"id": order_id})
        except PyMongoError as exc:
            raise DatabaseError("Unable to read order.") from exc
        if not record:
            raise OrderNotFoundError(f"Order '{order_id}' was not found.")
        return Order.from_record(record)

    def update_order_status(self, order_id: str, status: OrderStatus) -> Order:
        try:
            result = self.orders.find_one_and_update(
                {"id": order_id},
                {"$set": {"status": status}},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise DatabaseError("Unable to update order status.") from exc
        if not result:
            raise OrderNotFoundError(f"Order '{order_id}' was not found.")
        return Order.from_record(result)

    def save_verification_log(
        self,
        *,
        order_id: str,
        gmail_message_id: str,
        purpose: str,
        gmail_message_timestamp: datetime,
    ) -> None:
        record = VerificationLogRecord(
            order_id=order_id,
            gmail_message_id=gmail_message_id,
            purpose=purpose,
            verified_at=utcnow(),
            gmail_message_timestamp=ensure_utc(gmail_message_timestamp),
        )
        try:
            self.verification_logs.insert_one(record.to_dict())
        except PyMongoError as exc:
            raise DatabaseError("Unable to save verification log.") from exc

    def message_already_processed(self, gmail_message_id: str) -> bool:
        try:
            return self.verification_logs.find_one({"gmail_message_id": gmail_message_id}) is not None
        except PyMongoError as exc:
            raise DatabaseError("Unable to check verification log.") from exc
