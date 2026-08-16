"""Document Control - HTTP adapters only (NFR-MAINT.1)."""
import frappe

from buildpolaris_bff.shared.api_envelope import success, api_guard
from buildpolaris_bff.document_control.services import (
	annotation_service,
	drawing_revision_service,
	drawing_service,
	override_log_service,
)


@frappe.whitelist()
@api_guard
def register_drawing(project, drawing_number, title, discipline=None):
	return success(drawing_service.register_drawing(project, drawing_number, title, discipline))


@frappe.whitelist()
@api_guard
def list_drawings(project):
	return success(drawing_service.list_drawings(project))


@frappe.whitelist()
@api_guard
def add_revision(drawing, revision_code, file, issued_for=None, supersedes=None):
	return success(drawing_revision_service.add_revision(drawing, revision_code, file, issued_for, supersedes))


@frappe.whitelist()
@api_guard
def promote_revision(revision):
	return success(drawing_revision_service.promote_revision(revision))


@frappe.whitelist()
@api_guard
def get_current_revision(drawing):
	return success(drawing_revision_service.get_current_revision(drawing))


@frappe.whitelist()
@api_guard
def list_revisions(drawing):
	return success(drawing_revision_service.list_revisions(drawing))


@frappe.whitelist()
@api_guard
def add_annotation(revision, text, rfi=None, punch_item=None):
	return success(annotation_service.add_annotation(revision, text, rfi, punch_item))


@frappe.whitelist()
@api_guard
def list_annotations(revision):
	return success(annotation_service.list_annotations(revision))


@frappe.whitelist()
@api_guard
def get_revision_for_download(revision, override_reason=None):
	return success(override_log_service.get_revision_for_download(revision, override_reason))
