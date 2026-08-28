"""Custom exceptions used internally by the payment SDK."""

from __future__ import annotations


class PaymentTemplateError(Exception):
    """Base class for all payment SDK errors."""


class ConfigurationError(PaymentTemplateError):
    """Raised when required configuration is missing or invalid."""


class DatabaseError(PaymentTemplateError):
    """Raised when MongoDB operations fail."""


class GmailError(PaymentTemplateError):
    """Raised when Gmail IMAP operations fail."""


class OrderNotFoundError(PaymentTemplateError):
    """Raised when an order cannot be found."""


class OrderStateError(PaymentTemplateError):
    """Raised when an order is used in an invalid state."""


class VerificationError(PaymentTemplateError):
    """Raised when verification cannot be completed."""
