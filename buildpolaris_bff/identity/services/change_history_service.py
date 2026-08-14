"""
FR-1.6: any user with read access to a document sees its full field-level
change history, sourced from Frappe's native Version DocType.
"""
from buildpolaris_bff.shared.audit import get_history as _get_version_history


def get_change_history(doctype: str, name: str) -> list[dict]:
	"""Thin wrapper kept in identity/ for module-boundary clarity; the
	actual Version-log read + permission check lives in shared/audit.py
	since every module reuses it, not just identity."""
	return _get_version_history(doctype, name)
