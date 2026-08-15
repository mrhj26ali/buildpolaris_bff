"""
FR-7.5: closeout gates - final payment cannot issue until all Punch List
items are closed and all required Closeout Document categories are
collected. Cross-module invariant kept as SERVICE-LAYER CALLS into
field/financials, never a direct SQL join across module boundaries
(NFR-EXT.1).
"""
import frappe

from buildpolaris_bff.shared.exceptions import CloseoutGateError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role
from buildpolaris_bff.field.services.punch_list_service import list_punch_items
from buildpolaris_bff.financials.services.financial_close_service import has_unresolved_financial_items

REQUIRED_DOCUMENT_CATEGORIES = {"OMManual", "Warranty", "ConsentOfSurety", "ContractorAffidavit"}


def check_finalize_gate(closing_record: str, user: str | None = None) -> dict:
	"""Returns {"can_finalize": bool, "blockers": [...]}. Never a silent
	pass/fail - every blocking reason is enumerated for the UI to show."""
	doc = frappe.get_doc("Closing Record", closing_record)
	assert_project_permission(doc.project, ptype="read", user=user)

	blockers = []

	open_punch_items = [p for p in list_punch_items(doc.project, user=user) if p.status != "Closed"]
	if open_punch_items:
		blockers.append(f"{len(open_punch_items)} Punch List item(s) still open.")

	if has_unresolved_financial_items(doc.project):
		blockers.append("Unresolved financial items (Draft/Pending Commitments, Change Events, or Pay Applications).")

	existing_categories = {
		d.category for d in frappe.get_all(
			"Closeout Document", filters={"closing_record": closing_record}, fields=["category"]
		)
	}
	missing_categories = REQUIRED_DOCUMENT_CATEGORIES - existing_categories
	if missing_categories:
		blockers.append(f"Missing closeout document categories: {', '.join(sorted(missing_categories))}.")

	if doc.status != "SubstantiallyComplete":
		blockers.append("Substantial Completion Certificate not yet fully signed.")

	return {"can_finalize": not blockers, "blockers": blockers}


def finalize_closing_record(closing_record: str, finalized_by: str | None = None):
	"""The actual gate enforcement - raises CloseoutGateError enumerating
	every blocking reason rather than a generic 'denied' (FR-7.5)."""
	finalized_by = finalized_by or frappe.session.user
	doc = frappe.get_doc("Closing Record", closing_record)
	assert_project_permission(doc.project, ptype="write", user=finalized_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Accounting", "BuildPolaris Admin", user=finalized_by)

	gate = check_finalize_gate(closing_record, user=finalized_by)
	if not gate["can_finalize"]:
		raise CloseoutGateError("Cannot finalize closeout: " + "; ".join(gate["blockers"]))

	doc.status = "Finalized"
	doc.flags.via_gate = True
	doc.save()
	return doc.as_dict()


def check_final_payment_gate(project: str, user: str | None = None) -> dict:
	"""Used by financials/services/pay_application_service.py when
	approving a Pay Application flagged is_final=1 - the literal FR-7.5
	example ('final payment cannot issue until...')."""
	closing_record = frappe.db.get_value("Closing Record", {"project": project}, "name")
	if not closing_record:
		return {"can_pay": False, "blockers": ["No Closing Record has been opened for this Project yet."]}

	gate = check_finalize_gate(closing_record, user=user)
	return {"can_pay": gate["can_finalize"], "blockers": gate["blockers"]}
