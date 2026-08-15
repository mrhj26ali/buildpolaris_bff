"""FR-7.6: the closeout package exports as a single professional PDF
bundle using ERPNext v16's native Print Format + PDF engine (Chrome-based
rendering) - never a bespoke PDF library."""
import frappe
from frappe.utils.pdf import get_pdf

from buildpolaris_bff.shared.permissions import assert_project_permission

PRINT_FORMAT = "BuildPolaris Closeout Package"


def export_closeout_package(closing_record: str, user: str | None = None) -> dict:
	doc = frappe.get_doc("Closing Record", closing_record)
	assert_project_permission(doc.project, ptype="read", user=user)

	html = frappe.get_print("Closing Record", closing_record, print_format=PRINT_FORMAT)
	pdf_content = get_pdf(html)

	file_doc = frappe.get_doc({
		"doctype": "File",
		"file_name": f"{closing_record}-closeout-package.pdf",
		"attached_to_doctype": "Closing Record",
		"attached_to_name": closing_record,
		"content": pdf_content,
		"is_private": 1,
	})
	file_doc.insert(ignore_permissions=True)
	return {"file": file_doc.name, "file_url": file_doc.file_url}
