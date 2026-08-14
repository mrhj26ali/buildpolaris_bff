import frappe

from buildpolaris_bff.shared.security_log import log_security_event


def _get_client_ip() -> str:
	"""Best-effort client IP resolution, used only as a rate-limiting key,
	never as a security identity."""
	request = getattr(frappe.local, "request", None)
	if request:
		return getattr(request, "remote_addr", "unknown")
	return getattr(frappe.local, "request_ip", None) or "cli"


def is_rate_limited(action: str, limit: int = 5, seconds: int = 300) -> bool:
	"""Redis-backed rate limiter for unauthenticated/high-risk endpoints
	(register, activate, invite-accept - NFR-SEC.6). Intentionally does not
	touch normal authenticated CRUD flows.

	Returns True when the action should be rejected, False when allowed
	(and the counter was incremented).
	"""
	ip = _get_client_ip() or "unknown"
	key = f"bp_rate_limit:{action}:{ip}"
	cache = frappe.cache()

	try:
		val = cache.get_value(key)
		current = int(val) if val is not None else 0
	except Exception:
		current = 0

	if current >= limit:
		log_security_event(
			"RATE_LIMIT_EXCEEDED",
			{"action": action, "ip": ip, "limit": limit, "window_seconds": seconds},
		)
		return True

	try:
		cache.set_value(key, current + 1, expires_in_sec=seconds)
	except Exception:
		frappe.log_error(title="BuildPolaris Rate Limit Cache Error", message=frappe.get_traceback())

	return False
