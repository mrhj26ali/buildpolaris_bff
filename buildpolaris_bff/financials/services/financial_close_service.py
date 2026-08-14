"""
FR-3.6: budget vs committed vs actual, rolled up to the Project level
(Cost-Code-level detail lives in cost_code_service.get_budget_rollup).
Also the read used by the Closeout module's 'final payment gate' check
(FR-7.5) to confirm no financial item is left in an unresolved state.
"""
import frappe

from buildpolaris_bff.shared.permissions import assert_project_permission
from buildpolaris_bff.financials.services.cost_code_service import get_budget_rollup


def get_project_financial_summary(project: str, user: str | None = None) -> dict:
	assert_project_permission(project, ptype="read", user=user)
	rollup = get_budget_rollup(project, user=user)
	return {
		"project": project,
		"total_budget": sum(r["budget_amount"] or 0 for r in rollup),
		"total_committed": sum(r["committed"] or 0 for r in rollup),
		"total_actual": sum(r["actual"] or 0 for r in rollup),
		"cost_codes": rollup,
	}


def has_unresolved_financial_items(project: str) -> bool:
	"""Used by closeout/services/closeout_gate_service.py (FR-7.5) - the
	final payment gate is blocked while anything is still Draft/Pending."""
	pending_commitments = frappe.db.count("Commitment", {
		"project": project, "status": ["in", ["Draft", "PendingApproval"]],
	})
	pending_pay_apps = frappe.db.count("Pay Application", {
		"project": project, "status": ["in", ["Draft", "PendingApproval"]],
	})
	pending_changes = frappe.db.count("Change Event", {
		"project": project, "status": "Open",
	})
	return bool(pending_commitments or pending_pay_apps or pending_changes)
