"""
Idempotency-Key handling for PWA-originated writes (ARCH §4.1) and general
service-layer replay safety (NFR-SCALE.6).

`check_request`/`store_response` back a cache-based replay window for
synchronous REST writes carrying an `Idempotency-Key` header. Agent-gated
writes (FR-8.6) use their OWN durable, unique-indexed `idempotency_key`
column on `Agent Action Approval` (ERD §3.6) instead of this cache, because
that decision must survive a Redis flush - this module is NOT used for that
path; see ai_copilot/services/execution_service.py (Phase 2, later).
"""
import hashlib
import json

import frappe

from buildpolaris_bff.shared.exceptions import IdempotencyConflictError

_CACHE_PREFIX = "bp_idem"
_DEFAULT_TTL_SECONDS = 24 * 60 * 60


def _fingerprint(payload: dict) -> str:
	blob = json.dumps(payload, sort_keys=True, default=str)
	return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_key(idempotency_key: str) -> str:
	return f"{_CACHE_PREFIX}:{idempotency_key}"


def check_request(idempotency_key: str, request_payload: dict):
	"""Look up a prior response for this Idempotency-Key.

	Returns the cached response if this is a replay of the SAME request,
	None if unseen. Raises IdempotencyConflictError if the key is reused
	with a DIFFERENT payload (a client bug, not a legitimate retry).
	"""
	if not idempotency_key:
		return None

	cache = frappe.cache()
	raw = cache.get_value(_cache_key(idempotency_key))
	if not raw:
		return None

	try:
		record = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
	except Exception:
		return None

	if record.get("fingerprint") != _fingerprint(request_payload):
		raise IdempotencyConflictError(
			"Idempotency-Key reused with a different request payload."
		)

	return record.get("response")


def store_response(idempotency_key: str, request_payload: dict, response,
                    ttl_seconds: int = _DEFAULT_TTL_SECONDS):
	if not idempotency_key:
		return
	cache = frappe.cache()
	record = {"fingerprint": _fingerprint(request_payload), "response": response}
	cache.set_value(_cache_key(idempotency_key), json.dumps(record, default=str),
	                 expires_in_sec=ttl_seconds)


def idempotent_write(idempotency_key: str, request_payload: dict, fn,
                      ttl_seconds: int = _DEFAULT_TTL_SECONDS):
	"""Wrap a write call: replay-safe if idempotency_key is provided."""
	if idempotency_key:
		cached = check_request(idempotency_key, request_payload)
		if cached is not None:
			return cached

	result = fn()

	if idempotency_key:
		store_response(idempotency_key, request_payload, result, ttl_seconds)

	return result
