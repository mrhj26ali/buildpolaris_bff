"""FR-5.3: Field and PM users attach a text note to a drawing revision,
optionally linked to an RFI or Punch List item. The platform stores and
versions drawing FILES only - it never renders, views, or marks up their
contents (see REQ Out of Scope)."""
import frappe

from buildpolaris_bff.shared.permissions import assert_project_permission


def add_annotation(revision, text, rfi=None, punch_item=None, author=None):
	author = author or frappe.session.user
	revision_doc = frappe.get_doc("Drawing Revision", revision)
	drawing_doc = frappe.get_doc("Drawing", revision_doc.drawing)
	assert_project_permission(drawing_doc.project, ptype="write", user=author)

	doc = frappe.get_doc({
		"doctype": "Drawing Annotation",
		"revision": revision,
		"author": author,
		"text": text,
		"rfi": rfi,
		"punch_item": punch_item,
	})
	doc.insert()
	return doc.as_dict()


def list_annotations(revision: str, user: str | None = None):
	revision_doc = frappe.get_doc("Drawing Revision", revision)
	drawing_doc = frappe.get_doc("Drawing", revision_doc.drawing)
	assert_project_permission(drawing_doc.project, ptype="read", user=user)
	return frappe.get_all("Drawing Annotation", filters={"revision": revision},
	                       fields=["name", "author", "text", "rfi", "punch_item", "creation"],
	                       order_by="creation desc")
