"""FR-4.3: Document Controller issues Transmittals recording what was sent,
to whom, and when."""
import frappe
from frappe.utils import now_datetime

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def issue_transmittal(project, method, recipients, files, issued_by=None):
	"""recipients: [str, ...]; files: [<File doctype name>, ...] (already
	uploaded via Frappe's native File upload endpoint - FR-5.4)."""
	issued_by = issued_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=issued_by)
	assert_role("BuildPolaris Document Controller", "BuildPolaris Admin", user=issued_by)

	if not recipients:
		raise ValidationError("A Transmittal must have at least one recipient.")
	if not files:
		raise ValidationError("A Transmittal must reference at least one document.")

	for file_name in files:
		if not frappe.db.exists("File", file_name):
			raise ValidationError(f"File '{file_name}' does not exist.")

	doc = frappe.get_doc({
		"doctype": "Transmittal",
		"naming_series": "TX-.YYYY.-.#####",
		"project": project,
		"sent_by": issued_by,
		"sent_at": now_datetime(),
		"method": method,
	})
	for r in recipients:
		doc.append("recipients", {"recipient": r})
	for f in files:
		doc.append("documents", {"file": f})
	doc.insert()
	return doc.as_dict()


def list_transmittals(project: str, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	return frappe.get_all("Transmittal", filters={"project": project},
	                       fields=["name", "sent_by", "sent_at", "method"], order_by="sent_at desc")
