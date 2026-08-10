import datetime

import frappe
from frappe.utils import now_datetime

from buildpolaris_bff.shared.crypto_utils import generate_secure_token, verify_token


DEFAULT_TOKEN_TTL_HOURS = 24


def issue_single_use_token(
    ttl_hours: int = DEFAULT_TOKEN_TTL_HOURS,
) -> tuple[str, str, datetime.datetime]:
    """
    Issue a single-use token.

    Returns:
        raw_token: Token to be delivered once through a trusted channel.
        hashed_token: Token hash to persist in the database.
        expiry: Token expiry datetime.
    """
    raw_token, hashed_token = generate_secure_token()
    expiry = now_datetime() + datetime.timedelta(hours=ttl_hours)

    return raw_token, hashed_token, expiry


def is_expired(expiry) -> bool:
    """
    Return True when the given expiry value is in the past.
    """
    if not expiry:
        return False

    if isinstance(expiry, str):
        expiry = frappe.utils.get_datetime(expiry)

    return now_datetime() > expiry


def verify_single_use_token(raw_token: str, hashed_token: str, expiry) -> bool:
    """
    Verify token hash and expiry.
    """
    if not raw_token or not hashed_token:
        return False

    if is_expired(expiry):
        return False

    return verify_token(raw_token, hashed_token)
