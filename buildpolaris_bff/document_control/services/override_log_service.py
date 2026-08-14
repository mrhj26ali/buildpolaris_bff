"""
FR-5.5: Field users are blocked from downloading or acting on a superseded
drawing revision without an explicit, logged override reason. The log is a
structured security event (shared/security_log.py) rather than a bespoke
doctype outside ERD §3.3's schema - queryable via Error Log, consistent
with every other security-relevant event on the platform.
"""
import frappe

from buildpolaris_bff.shared.exceptions import PermissionDeniedError
from buildpolaris_bff.shared.permissions import assert_project_permission
from buildpolaris_bff.shared.security_log import log_security_event


def get_revision_for_download(revision: str, override_reason: str | None = None, user: str | None = None) -> dict:
	"""Returns the revision's download metadata. Raises unless the revision
	is current, OR an explicit override reason is supplied - which is then
	logged, never silently allowed through."""
	user = user or frappe.session.user
	doc = frappe.get_doc("Drawing Revision", revision)
	project = frappe.db.get_value("Drawing", doc.drawing, "project")
	assert_project_permission(project, ptype="read", user=user)

	if not doc.is_current:
		if not override_reason:
			raise PermissionDeniedError(
				"This is a superseded revision. Provide an explicit override "
				"reason to proceed (FR-5.5).",
				error_code="SUPERSEDED_REVISION_BLOCKED",
			)
		log_security_event("SUPERSEDED_REVISION_OVERRIDE", {
			"revision": revision, "drawing": doc.drawing, "user": user, "reason": override_reason,
		})

	return {
		"revision": revision, "is_current": doc.is_current,
		"file": doc.file, "issued_for": doc.issued_for,
	}
