"""Purpose generation for payment verification."""

from __future__ import annotations

from .utils import generate_secure_suffix, slugify_upper, utcnow


def generate_purpose(prefix: str) -> str:
    """Generate a secure purpose string in the required format."""

    normalized_prefix = slugify_upper(prefix)
    date_part = utcnow().strftime("%Y%m%d")
    suffix = generate_secure_suffix(6)
    return f"{normalized_prefix}-{date_part}-{suffix}"
