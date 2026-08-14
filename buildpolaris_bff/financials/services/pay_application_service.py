"""FR-3.5: AIA G702/G703-style Pay Applications billed against a
Commitment. Approval generates a native Purchase Invoice with retainage as
a held-back Payment Term; payment generates a Payment Entry."""
import frappe
from frappe.utils import flt

from buildpolaris_bff.shared.erpnext_adapter import (
	create_payment_entry,
	create_purchase_invoice_with_retainage,
	get_or_create_billing_item,
)
from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role
from buildpolaris_bff.shared.security_log import log_security_event


def create_pay_application(commitment, period_end, lines, retainage_pct=10, created_by=None):
	"""lines: [{cost_code, scheduled_value, work_completed_this_period, materials_stored}]"""
	created_by = created_by or frappe.session.user
	commitment_doc = frappe.get_doc("Commitment", commitment)
	assert_project_permission(commitment_doc.project, ptype="write", user=created_by)
	assert_role("BuildPolaris Subcontractor", "BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	if commitment_doc.status != "Approved":
		raise ValidationError("Pay Applications can only be billed against an Approved Commitment.")

	doc = frappe.get_doc({
		"doctype": "Pay Application",
		"naming_series": "PA-.YYYY.-.#####",
		"commitment": commitment,
		"project": commitment_doc.project,
		"period_end": period_end,
		"retainage_pct": retainage_pct,
		"status": "Draft",
	})
	for line in lines:
		scheduled = flt(line.get("scheduled_value"))
		completed = flt(line.get("work_completed_this_period"))
		stored = flt(line.get("materials_stored"))
		pct = round(((completed + stored) / scheduled) * 100, 2) if scheduled else 0
		doc.append("lines", {
			"cost_code": line.get("cost_code"),
			"scheduled_value": scheduled,
			"work_completed_this_period": completed,
			"materials_stored": stored,
			"pct_complete": pct,
		})
	doc.insert()
	return doc.as_dict()


def submit_for_approval(pay_application: str, submitted_by: str | None = None):
	submitted_by = submitted_by or frappe.session.user
	doc = frappe.get_doc("Pay Application", pay_application)
	assert_project_permission(doc.project, ptype="write", user=submitted_by)
	if doc.status != "Draft":
		raise ValidationError(f"Pay Application must be Draft to submit (current: {doc.status}).")
	doc.status = "PendingApproval"
	doc.save()
	return doc.as_dict()


def approve_pay_application(pay_application: str, approved_by: str | None = None):
	"""FR-3.5: approval generates a native Purchase Invoice with retainage
	as a held-back Payment Term."""
	approved_by = approved_by or frappe.session.user
	assert_role("BuildPolaris Accounting", "BuildPolaris Admin", user=approved_by)

	doc = frappe.get_doc("Pay Application", pay_application)
	assert_project_permission(doc.project, ptype="write", user=approved_by)

	if doc.status != "PendingApproval":
		raise ValidationError(f"Pay Application must be PendingApproval to approve (current: {doc.status}).")

	commitment_doc = frappe.get_doc("Commitment", doc.commitment)
	company = frappe.db.get_value("Project", doc.project, "company")

	items = []
	for line in doc.lines:
		item_code = get_or_create_billing_item(line.cost_code)
		items.append({
			"item_code": item_code,
			"description": f"Pay App {doc.name} - {line.cost_code}",
			"qty": 1,
			"rate": flt(line.work_completed_this_period) + flt(line.materials_stored),
		})

	pi_name = create_purchase_invoice_with_retainage(
		company=company, supplier=commitment_doc.supplier, project=doc.project,
		items=items, retainage_pct=doc.retainage_pct,
		purchase_order=commitment_doc.purchase_order,
	)

	doc.purchase_invoice = pi_name
	doc.status = "Approved"
	doc.save()

	log_security_event("PAY_APPLICATION_APPROVED", {"pay_application": pay_application, "purchase_invoice": pi_name})
	frappe.db.commit()
	return doc.as_dict()


def record_payment(pay_application: str, paid_amount: float | None = None, recorded_by: str | None = None):
	recorded_by = recorded_by or frappe.session.user
	assert_role("BuildPolaris Accounting", "BuildPolaris Admin", user=recorded_by)

	doc = frappe.get_doc("Pay Application", pay_application)
	assert_project_permission(doc.project, ptype="write", user=recorded_by)

	if doc.status != "Approved":
		raise ValidationError(f"Pay Application must be Approved before recording payment (current: {doc.status}).")
	if not doc.purchase_invoice:
		raise ValidationError("Pay Application has no linked Purchase Invoice.")

	pe_name = create_payment_entry(doc.purchase_invoice, paid_amount=paid_amount)
	doc.payment_entry = pe_name
	doc.status = "Paid"
	doc.save()

	log_security_event("PAY_APPLICATION_PAID", {"pay_application": pay_application, "payment_entry": pe_name})
	frappe.db.commit()
	return doc.as_dict()
