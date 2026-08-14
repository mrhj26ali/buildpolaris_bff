"""FR-4.2: Submittal Packages with individual line items, tracked through
a review workflow."""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission


def create_submittal(project, spec_section, lines, created_by=None):
	"""lines: [{description}]"""
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)

	if not lines:
		raise ValidationError("A Submittal Package requires at least one line item.")

	doc = frappe.get_doc({
		"doctype": "Submittal Package",
		"naming_series": "SUB-.YYYY.-.#####",
		"project": project,
		"spec_section": spec_section,
		"status": "Submitted",
	})
	for line in lines:
		doc.append("lines", {"description": line.get("description"), "status": "Pending"})
	doc.insert()
	return doc.as_dict()


def review_line(submittal: str, line_name: str, status: str, reviewer: str | None = None):
	"""status: Approved | Revise | Rejected."""
	reviewer = reviewer or frappe.session.user
	doc = frappe.get_doc("Submittal Package", submittal)
	assert_project_permission(doc.project, ptype="write", user=reviewer)

	valid_statuses = {"Pending", "Approved", "Revise", "Rejected"}
	if status not in valid_statuses:
		raise ValidationError(f"status must be one of {valid_statuses}.")

	line = next((l for l in doc.lines if l.name == line_name), None)
	if not line:
		raise ValidationError(f"Line item {line_name} not found on this Submittal Package.")

	line.status = status
	line.reviewer = reviewer
	_recompute_package_status(doc)
	doc.save()
	return doc.as_dict()


def _recompute_package_status(doc):
	statuses = {l.status for l in doc.lines}
	if statuses == {"Approved"}:
		doc.status = "Approved"
	elif "Rejected" in statuses:
		doc.status = "Rejected"
	elif "Revise" in statuses:
		doc.status = "ResubmitRequested"
	elif "Pending" in statuses and len(statuses) > 1:
		doc.status = "UnderReview"
	# all-Pending stays "Submitted"


def list_submittals(project: str, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	return frappe.get_all("Submittal Package", filters={"project": project},
	                       fields=["name", "spec_section", "status"])
