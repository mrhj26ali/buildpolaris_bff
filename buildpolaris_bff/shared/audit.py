"""
FR-1.6: any user with read access to a document sees its full field-level
change history, sourced from Frappe's native Version DocType - never a
custom audit-log table (ERD §2).
"""
import json

import frappe

from buildpolaris_bff.shared.security_log import log_security_event


@frappe.whitelist()
def get_history(doctype: str, name: str):
	"""Role: any user with read access to the target document (FR-1.6)."""
	if not frappe.has_permission(doctype, "read", name):
		log_security_event(
			"UNAUTHORIZED_HISTORY_ACCESS",
			{"user": frappe.session.user, "doctype": doctype, "docname": name},
		)
		frappe.throw("Forbidden", frappe.PermissionError)

	versions = frappe.get_all(
		"Version",
		filters={"ref_doctype": doctype, "docname": name},
		fields=["owner", "creation", "data"],
		order_by="creation desc",
		limit=100,
		ignore_permissions=True,  # access already checked above
	)

	out = []
	for v in versions:
		changes = []
		try:
			data = json.loads(v.data) if isinstance(v.data, str) else v.data
			for entry in data.get("changed") or []:
				field_name, before, after = entry
				changes.append({"field": field_name, "before": before, "after": after})
		except Exception:
			pass
		out.append({"owner": v.owner, "creation": v.creation, "changes": changes})
	return out
