"""FR-3.4: Change Events, optionally linked to an originating RFI. Approval
updates the linked Commitment's revised amount - the defined amendment
path for Commitment (FR-3.8)."""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role
from buildpolaris_bff.shared.security_log import log_security_event

VALID_CATEGORIES = {"ScopeGap", "DesignError", "FieldCondition", "OwnerRequest", "Other"}


def create_change_event(project, commitment, category, outcome_reason, amount_delta,
                         originating_rfi=None, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	if category not in VALID_CATEGORIES:
		raise ValidationError(f"category must be one of {VALID_CATEGORIES}.")

	commit_project = frappe.db.get_value("Commitment", commitment, "project")
	if commit_project != project:
		raise ValidationError("Commitment does not belong to this Project.")

	doc = frappe.get_doc({
		"doctype": "Change Event",
		"naming_series": "CE-.YYYY.-.#####",
		"project": project,
		"commitment": commitment,
		"originating_rfi": originating_rfi,
		"category": category,
		"outcome_reason": outcome_reason,
		"amount_delta": amount_delta,
		"status": "Open",
	})
	doc.insert()
	return doc.as_dict()


def approve_change_event(change_event: str, approved_by: str | None = None):
	"""FR-3.4: Role: Owner or PM (unlike Commitment approval, which is
	Accounting-only - this is a scope decision, not a payment decision)."""
	approved_by = approved_by or frappe.session.user
	assert_role("BuildPolaris Owner", "BuildPolaris Project Manager", "BuildPolaris Admin", user=approved_by)

	doc = frappe.get_doc("Change Event", change_event)
	assert_project_permission(doc.project, ptype="write", user=approved_by)

	if doc.status != "Open":
		raise ValidationError(f"Change Event must be Open to approve (current: {doc.status}).")

	commitment_doc = frappe.get_doc("Commitment", doc.commitment)
	commitment_doc.flags.via_amendment = True  # a Change Event IS the defined amendment path (FR-3.8)
	commitment_doc.revised_amount = (commitment_doc.revised_amount or 0) + doc.amount_delta
	commitment_doc.save()

	doc.status = "Approved"
	doc.approved_by = approved_by
	doc.is_immutable = 1
	doc.save()

	log_security_event("CHANGE_EVENT_APPROVED", {
		"change_event": change_event, "commitment": doc.commitment, "amount_delta": doc.amount_delta,
	})
	frappe.db.commit()
	return doc.as_dict()


def reject_change_event(change_event: str, rejected_by: str | None = None):
	rejected_by = rejected_by or frappe.session.user
	assert_role("BuildPolaris Owner", "BuildPolaris Project Manager", "BuildPolaris Admin", user=rejected_by)

	doc = frappe.get_doc("Change Event", change_event)
	assert_project_permission(doc.project, ptype="write", user=rejected_by)
	if doc.status != "Open":
		raise ValidationError(f"Change Event must be Open to reject (current: {doc.status}).")
	doc.status = "Rejected"
	doc.is_immutable = 1
	doc.save()
	return doc.as_dict()
def list_change_events(project):
	from buildpolaris_bff.shared.permissions import assert_project_permission
	assert_project_permission(project, ptype="read")
	return frappe.get_all("Change Event",
		filters={"project": project},
		fields=["name", "commitment", "category", "amount_delta", "outcome_reason", "status", "creation"],
		order_by="creation desc",
	)