"""
Standard API response envelope - the "shaping the response envelope"
duty of api.py per ARCH §3.1.

Wire contract (must match buildpolaris_pwa/src/types/api.ts exactly -
that file is the frontend's compile-time source of truth for this shape):

    { "success": bool, "data": <T> | null, "message": str, "error_code"?: str }

Every whitelisted endpoint should be decorated with @api_guard and return
success(...) - api_guard converts any raised BuildPolarisError (or bare
frappe.PermissionError) into the same envelope shape with success=false,
so buildpolaris_pwa's bffClient.ts can handle every response - success
or failure - through one code path (isBffEnvelope()) instead of having
to separately parse Frappe's own generic exception body.
"""
import functools

import frappe

from buildpolaris_bff.shared.exceptions import BuildPolarisError
from buildpolaris_bff.shared.security_log import get_trace_id


def success(data=None, message: str = ""):
	return {
		"success": True,
		"data": data,
		"message": message,
		"trace_id": get_trace_id(),
	}


def error(err: BuildPolarisError):
	return {
		"success": False,
		"data": None,
		"message": err.message,
		"error_code": err.error_code,
		"trace_id": get_trace_id(),
	}


def paginated(rows: list, total: int, page: int, page_size: int, message: str = ""):
	"""Matches buildpolaris_pwa's PaginatedResult<T> - a flat
	{items, total, page, page_size} shape, not a nested "pagination"
	object."""
	return success({
		"items": rows,
		"total": total,
		"page": page,
		"page_size": page_size,
	}, message=message)


def api_guard(fn):
	"""Apply directly under @frappe.whitelist() on every endpoint:

		@frappe.whitelist()
		@api_guard
		def my_endpoint(...):
			...
			return success(result)

	Catches BuildPolarisError (and frappe.PermissionError, so a bare
	frappe.throw(..., frappe.PermissionError) from deep in a services/
	call still reaches the PWA as a structured envelope) and reshapes it
	into the same {success:false, ...} envelope, with the right HTTP
	status code set for observability. Anything else propagates
	unchanged - Frappe's own handler still serializes truly unexpected
	exceptions, and buildpolaris_pwa's extractServerMessage() already has
	a fallback path for that shape.
	"""
	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except BuildPolarisError as err:
			frappe.local.response["http_status_code"] = err.http_status_code
			frappe.clear_messages()
			return error(err)
		except frappe.PermissionError as err:
			from buildpolaris_bff.shared.exceptions import PermissionDeniedError
			mapped = PermissionDeniedError(str(err) or "Permission denied.")
			frappe.local.response["http_status_code"] = mapped.http_status_code
			frappe.clear_messages()
			return error(mapped)
	return wrapper
