"""
FR-5.1/FR-5.2: versioned Revisions that supersede rather than overwrite;
only an explicitly authorized revision (e.g. "Issued for Construction")
may be promoted to current, enforced server-side.
"""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def add_revision(drawing, revision_code, file, issued_for=None, supersedes=None, created_by=None):
	created_by = created_by or frappe.session.user
	drawing_doc = frappe.get_doc("Drawing", drawing)
	assert_project_permission(drawing_doc.project, ptype="write", user=created_by)
	assert_role("BuildPolaris Document Controller", "BuildPolaris Admin", user=created_by)

	if supersedes:
		superseded_drawing = frappe.db.get_value("Drawing Revision", supersedes, "drawing")
		if superseded_drawing != drawing:
			raise ValidationError("'supersedes' must reference a revision of the SAME Drawing.")

	if not frappe.db.exists("File", file):
		raise ValidationError(f"File '{file}' does not exist.")

	doc = frappe.get_doc({
		"doctype": "Drawing Revision",
		"naming_series": "REV-.YYYY.-.#####",
		"drawing": drawing,
		"revision_code": revision_code,
		"file": file,
		"issued_for": issued_for,
		"supersedes": supersedes,
		"is_current": 0,
	})
	doc.insert()
	return doc.as_dict()


def promote_revision(revision: str, promoted_by: str | None = None):
	"""FR-5.2: the ONLY path by which is_current becomes true. Demotes any
	other revision of the same Drawing currently marked current."""
	promoted_by = promoted_by or frappe.session.user
	doc = frappe.get_doc("Drawing Revision", revision)
	drawing_doc = frappe.get_doc("Drawing", doc.drawing)
	assert_project_permission(drawing_doc.project, ptype="write", user=promoted_by)
	assert_role("BuildPolaris Document Controller", "BuildPolaris Admin", user=promoted_by)

	currently_current = frappe.get_all(
		"Drawing Revision", filters={"drawing": doc.drawing, "is_current": 1}, pluck="name",
	)
	for other in currently_current:
		if other != revision:
			other_doc = frappe.get_doc("Drawing Revision", other)
			other_doc.is_current = 0
			other_doc.flags.via_promotion = True
			other_doc.save()

	doc.is_current = 1
	doc.flags.via_promotion = True
	doc.save()
	return doc.as_dict()


def get_current_revision(drawing: str, user: str | None = None):
	drawing_doc = frappe.get_doc("Drawing", drawing)
	assert_project_permission(drawing_doc.project, ptype="read", user=user)
	return frappe.db.get_value(
		"Drawing Revision", {"drawing": drawing, "is_current": 1},
		["name", "revision_code", "file", "issued_for"], as_dict=True,
	)


def list_revisions(drawing: str, user: str | None = None):
	drawing_doc = frappe.get_doc("Drawing", drawing)
	assert_project_permission(drawing_doc.project, ptype="read", user=user)
	return frappe.get_all("Drawing Revision", filters={"drawing": drawing},
	                       fields=["name", "revision_code", "is_current", "issued_for", "supersedes"],
	                       order_by="creation desc")
