import json

import frappe


def log_security_event(event_type: str, details: dict):
	"""FR-1.5 (v1) — structured security events into Error Log.
	Dedicated Security Event doctype is Phase 2 (documented)."""
	frappe.log_error(
		title=f"[SECURITY] {event_type}",
		message=json.dumps(details, indent=2, default=str),
	)