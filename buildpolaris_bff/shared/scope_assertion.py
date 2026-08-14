"""
Short-TTL, request-scoped Scope Assertion for the BFF <-> AI sidecar
boundary (ARCH §4.2). NOT a general-purpose auth token, and never sent to
the browser - it narrows an already-permission-checked BFF request into a
signed payload the AI sidecar trusts without a MariaDB round-trip per query.

A Scope Assertion can only NARROW scope: it is minted after the caller's own
has_permission check has already passed, so a stolen/replayed assertion
cannot grant a permission the acting user's Role doesn't already have.
"""
import base64
import hashlib
import hmac
import json
import time

import frappe

from buildpolaris_bff.shared.exceptions import ScopeAssertionError

_DEFAULT_TTL_SECONDS = 60


def _signing_key() -> bytes:
	# Frappe's own site-level secret - no new secret to provision/rotate.
	secret = frappe.conf.get("encryption_key") or frappe.conf.get("secret_key")
	if not secret:
		frappe.throw("Site is missing an encryption_key - required for Scope Assertions.")
	return secret.encode("utf-8")


def _b64(data: bytes) -> str:
	return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _unb64(data: str) -> bytes:
	padding = "=" * (-len(data) % 4)
	return base64.urlsafe_b64decode(data + padding)


def mint_scope_assertion(project: str | None, user: str | None = None,
                          ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> str:
	"""Mint a signed Scope Assertion for the current (already permission-
	checked) request. Call this ONLY after frappe.has_permission has passed."""
	user = user or frappe.session.user
	company = None
	if frappe.db.has_column("User", "bp_company"):
		company = frappe.db.get_value("User", user, "bp_company")
	roles = frappe.get_roles(user)

	claims = {
		"company": company,
		"project": project,
		"user": user,
		"role": roles,
		"expires_at": int(time.time()) + ttl_seconds,
	}
	body = json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
	signature = hmac.new(_signing_key(), body, hashlib.sha256).digest()
	return f"{_b64(body)}.{_b64(signature)}"


def verify_scope_assertion(token: str) -> dict:
	"""Verify a Scope Assertion's signature and expiry. buildpolaris_ai
	mirrors this exact check in Python; this is the reference implementation."""
	try:
		body_b64, sig_b64 = token.split(".", 1)
		body = _unb64(body_b64)
		signature = _unb64(sig_b64)
	except Exception:
		raise ScopeAssertionError("Malformed scope assertion.")

	expected_signature = hmac.new(_signing_key(), body, hashlib.sha256).digest()
	if not hmac.compare_digest(signature, expected_signature):
		raise ScopeAssertionError("Scope assertion signature mismatch.")

	claims = json.loads(body)
	if claims.get("expires_at", 0) < int(time.time()):
		raise ScopeAssertionError("Scope assertion expired.")

	return claims
