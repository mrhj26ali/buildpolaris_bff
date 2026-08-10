import frappe
from frappe import _

from buildpolaris_bff.shared.security_log import log_security_event


def _get_client_ip() -> str:
    """
    Best-effort client IP resolution.
    This is used only as a rate-limiting key, not as a security identity.
    """
    request = getattr(frappe.local, "request", None)

    if request:
        return getattr(request, "remote_addr", "unknown")

    return getattr(frappe.local, "request_ip", None) or "cli"


def is_rate_limited(action: str, limit: int = 5, seconds: int = 300) -> bool:
    """
    Simple Redis-backed rate limiter for sensitive endpoints.

    This intentionally avoids blocking normal authenticated CRUD flows.
    It is meant for unauthenticated or high-risk actions such as:
      - tenant registration
      - account activation
      - activation resend

    Returns:
        True when the action should be rejected.
        False when the action is allowed and the counter was incremented.
    """
    ip = _get_client_ip() or "unknown"
    key = f"bp_rate_limit:{action}:{ip}"
    cache = frappe.cache()

    current = 0
    try:
        if hasattr(cache, "get_value"):
            val = cache.get_value(key)
        elif hasattr(cache, "get"):
            val = cache.get(key)
        else:
            val = None
            
        current = int(val) if val is not None else 0
    except Exception:
        current = 0

    if current >= limit:
        log_security_event(
            "RATE_LIMIT_EXCEEDED",
            {
                "action": action,
                "ip": ip,
                "limit": limit,
                "window_seconds": seconds,
            },
        )
        return True

    next_value = current + 1

    try:
        if hasattr(cache, "set_value"):
            cache.set_value(key, next_value, expires_in_sec=seconds)
        elif hasattr(cache, "set"):
            cache.set(key, next_value, ex=seconds)
        else:
            cache[key] = next_value
    except Exception:
        # If cache fails, we fail open (allow request) but log it
        frappe.log_error(
            title="BuildPolaris Rate Limit Cache Error",
            message=frappe.get_traceback(),
        )

    return False
