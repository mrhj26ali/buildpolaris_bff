"""
Standard API response envelope - the "shaping the response envelope" duty
of api.py per ARCH §3.1.

Every whitelisted endpoint returns success(...); a raised BuildPolarisError
is allowed to propagate and shared/exceptions.py's to_frappe_exception()
maps it to the right HTTP status.
"""
import frappe

from buildpolaris_bff.shared.exceptions import BuildPolarisError, to_frappe_exception
from buildpolaris_bff.shared.security_log import get_trace_id


def success(data=None, message: str | None = None):
	envelope = {"ok": True, "trace_id": get_trace_id()}
	if data is not None:
		envelope["data"] = data
	if message:
		envelope["message"] = message
	return envelope


def paginated(rows: list, total: int, page: int, page_size: int):
	return success({
		"rows": rows,
		"pagination": {"page": page, "page_size": page_size, "total": total},
	})


def handle_api_exception(fn):
	"""Optional decorator converting a BuildPolarisError into a clean
	frappe exception with the right HTTP status. Most api.py functions
	don't need this explicitly - Frappe's global exception handler already
	renders any raised exception."""
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except BuildPolarisError as err:
			frappe.local.response["http_status_code"] = err.http_status_code
			raise to_frappe_exception(err)
	wrapper.__name__ = fn.__name__
	wrapper.__doc__ = fn.__doc__
	return wrapper
