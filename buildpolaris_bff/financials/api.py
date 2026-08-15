"""Financials - HTTP adapters only (NFR-MAINT.1)."""
import frappe

from buildpolaris_bff.shared.api_envelope import success
from buildpolaris_bff.financials.services import (
	amendment_service,
	change_event_service,
	commitment_service,
	cost_code_service,
	evm_service,
	financial_close_service,
	pay_application_service,
)


@frappe.whitelist()
def create_cost_code(project, code, description, budget_amount, cost_center=None):
	return success(cost_code_service.create_cost_code(project, code, description, float(budget_amount), cost_center))


@frappe.whitelist()
def list_cost_codes(project):
	return success(cost_code_service.list_cost_codes(project))


@frappe.whitelist()
def get_budget_rollup(project):
	return success(cost_code_service.get_budget_rollup(project))


@frappe.whitelist()
def create_commitment(project, cost_code, supplier, type, original_amount):
	return success(commitment_service.create_commitment(project, cost_code, supplier, type, float(original_amount)))


@frappe.whitelist()
def submit_commitment_for_approval(commitment):
	return success(commitment_service.submit_for_approval(commitment))


@frappe.whitelist()
def approve_commitment(commitment, items=None):
	if isinstance(items, str):
		items = frappe.parse_json(items)
	return success(commitment_service.approve_commitment(commitment, items))


@frappe.whitelist()
def create_change_event(project, commitment, category, outcome_reason, amount_delta, originating_rfi=None):
	return success(change_event_service.create_change_event(
		project, commitment, category, outcome_reason, float(amount_delta), originating_rfi
	))


@frappe.whitelist()
def approve_change_event(change_event):
	return success(change_event_service.approve_change_event(change_event))


@frappe.whitelist()
def reject_change_event(change_event):
	return success(change_event_service.reject_change_event(change_event))


@frappe.whitelist()
def create_pay_application(commitment, period_end, lines, retainage_pct=10, is_final=0):
	if isinstance(lines, str):
		lines = frappe.parse_json(lines)
	return success(pay_application_service.create_pay_application(
		commitment, period_end, lines, float(retainage_pct), int(is_final)
	))


@frappe.whitelist()
def submit_pay_application_for_approval(pay_application):
	return success(pay_application_service.submit_for_approval(pay_application))


@frappe.whitelist()
def approve_pay_application(pay_application):
	return success(pay_application_service.approve_pay_application(pay_application))


@frappe.whitelist()
def record_payment(pay_application, paid_amount=None):
	paid_amount = float(paid_amount) if paid_amount is not None else None
	return success(pay_application_service.record_payment(pay_application, paid_amount))


@frappe.whitelist()
def get_evm(project, as_of_date=None):
	return success(evm_service.compute_evm(project, as_of_date))


@frappe.whitelist()
def get_project_financial_summary(project):
	return success(financial_close_service.get_project_financial_summary(project))


@frappe.whitelist()
def create_offsetting_change_event(original_change_event, reason):
	return success(amendment_service.create_offsetting_change_event(original_change_event, reason))


@frappe.whitelist()
def get_amendment_history(doctype, name):
	return success(amendment_service.get_amendment_history(doctype, name))
