"""
Structured security logging and request correlation (NFR-SEC.5, NFR-OBS.1).

log_security_event() -> queryable, structured security-relevant events
(auth, Role changes, unauthorized access attempts) into Frappe's native
Error Log - satisfies "structured, queryable" without a bespoke doctype.

attach_trace_id() is wired via hooks.before_request so every request gets a
trace_id that threads PWA -> BFF -> AI sidecar (NFR-OBS.1). Observability's
trace-id responsibility lives here (folded in per ARCH §6.1 point 8, rather
than a separate shared/observability.py) since every structured log line
needs the same trace id this module already owns.
"""
import json
import uuid

import frappe

TRACE_HEADER = "X-BP-Trace-Id"


def attach_trace_id(*args, **kwargs):
	"""before_request hook: attach (or inherit) a trace id to frappe.local."""
	if getattr(frappe.local, "bp_trace_id", None):
		return frappe.local.bp_trace_id

	incoming = None
	request = getattr(frappe.local, "request", None)
	if request:
		incoming = request.headers.get(TRACE_HEADER)

	frappe.local.bp_trace_id = incoming or str(uuid.uuid4())
	return frappe.local.bp_trace_id


def get_trace_id() -> str:
	return getattr(frappe.local, "bp_trace_id", None) or "unknown"


def log_security_event(event_type: str, details: dict):
	"""Structured security event -> Frappe's native Error Log (NFR-SEC.5)."""
	payload = dict(details)
	payload["trace_id"] = get_trace_id()
	payload["user"] = frappe.session.user if frappe.session else "unknown"
	frappe.log_error(
		title=f"[SECURITY] {event_type}",
		message=json.dumps(payload, indent=2, default=str),
	)


def log_structured(event: str, details: dict):
	"""General structured log line (never a print statement, NFR-OBS.1)."""
	payload = dict(details)
	payload["trace_id"] = get_trace_id()
	frappe.log_error(title=f"[BP:{event}]", message=json.dumps(payload, default=str))
