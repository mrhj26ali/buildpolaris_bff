"""
FR-3.8: the defined amendment flow for approved, immutable financial
records. There is no generic "unlock and edit" path - each doctype's
correction flow is intentionally narrow and fully audited:

  - Commitment  -> corrected via an approved Change Event (amount only).
    Any other correction (wrong Supplier, wrong Cost Code) requires
    Accounting to reject the approval upstream before it becomes
    immutable; once immutable, no field but revised_amount ever changes,
    and only through change_event_service.approve_change_event.

  - Change Event -> once Approved/Rejected, itself immutable; a mistaken
    approval is corrected by logging an offsetting Change Event (negative
    amount_delta) rather than editing history - this preserves the full,
    truthful chain (NFR-AUD.1) instead of rewriting what happened.

  - Pay Application -> once Approved/Paid, corrected by creating a new
    Pay Application against the same Commitment for a later period that
    nets out the error, never by re-opening the original.
"""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role
from buildpolaris_bff.identity.services import change_history_service


def create_offsetting_change_event(original_change_event: str, reason: str, created_by: str | None = None):
	"""The concrete corrective action for an erroneously approved Change
	Event: an equal-and-opposite Change Event, fully traceable via
	get_amendment_history()."""
	created_by = created_by or frappe.session.user
	original = frappe.get_doc("Change Event", original_change_event)
	assert_project_permission(original.project, ptype="write", user=created_by)
	assert_role("BuildPolaris Owner", "BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	if original.status != "Approved":
		raise ValidationError("Only an Approved Change Event can be offset.")

	from buildpolaris_bff.financials.services.change_event_service import create_change_event

	return create_change_event(
		project=original.project,
		commitment=original.commitment,
		category=original.category,
		outcome_reason=f"Amendment of {original.name}: {reason}",
		amount_delta=-original.amount_delta,
		created_by=created_by,
	)


def get_amendment_history(doctype: str, name: str):
	"""Every amendment is itself a fully versioned write (FR-1.6/NFR-AUD.1) -
	surface it through the same native Version history, not a parallel log."""
	return change_history_service.get_change_history(doctype, name)
