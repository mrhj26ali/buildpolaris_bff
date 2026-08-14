"""FR-3.2/FR-3.3: Commitments against a Cost Code + native Supplier,
approved by Accounting."""
import frappe
from frappe.utils import now_datetime

from buildpolaris_bff.shared.erpnext_adapter import create_purchase_order, get_or_create_cost_center
from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role
from buildpolaris_bff.shared.security_log import log_security_event


def create_commitment(project, cost_code, supplier, type, original_amount, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	if type not in ("Subcontract", "PurchaseOrder"):
		raise ValidationError("type must be 'Subcontract' or 'PurchaseOrder'.")

	cc_project = frappe.db.get_value("Cost Code", cost_code, "project")
	if cc_project != project:
		raise ValidationError("Cost Code does not belong to this Project.")

	doc = frappe.get_doc({
		"doctype": "Commitment",
		"naming_series": "COMM-.YYYY.-.#####",
		"project": project,
		"cost_code": cost_code,
		"supplier": supplier,
		"type": type,
		"status": "Draft",
		"original_amount": original_amount,
		"revised_amount": original_amount,
	})
	doc.insert()
	return doc.as_dict()


def submit_for_approval(commitment: str, submitted_by: str | None = None):
	submitted_by = submitted_by or frappe.session.user
	doc = frappe.get_doc("Commitment", commitment)
	assert_project_permission(doc.project, ptype="write", user=submitted_by)
	if doc.status != "Draft":
		raise ValidationError(f"Commitment must be Draft to submit for approval (current: {doc.status}).")
	doc.status = "PendingApproval"
	doc.save()
	return doc.as_dict()


def approve_commitment(commitment: str, items: list | None = None, approved_by: str | None = None):
	"""FR-3.3: approval rolls the amount into the Cost Code's committed
	total (read live via get_committed_total below - no duplicated rollup
	field) and, for PO-type Commitments, creates and links a native
	Purchase Order."""
	approved_by = approved_by or frappe.session.user
	assert_role("BuildPolaris Accounting", "BuildPolaris Admin", user=approved_by)

	doc = frappe.get_doc("Commitment", commitment)
	assert_project_permission(doc.project, ptype="write", user=approved_by)

	if doc.status != "PendingApproval":
		raise ValidationError(f"Commitment must be PendingApproval to approve (current: {doc.status}).")

	if doc.type == "PurchaseOrder":
		if not items:
			raise ValidationError("PO-type Commitments require line items to create the Purchase Order.")
		company = frappe.db.get_value("Project", doc.project, "company")
		cost_center = get_or_create_cost_center(company)
		po_name = create_purchase_order(company, doc.supplier, doc.project, items, cost_center=cost_center)
		doc.purchase_order = po_name

	doc.status = "Approved"
	doc.approved_by = approved_by
	doc.approved_at = now_datetime()
	doc.is_immutable = 1
	doc.save()

	log_security_event("COMMITMENT_APPROVED", {"commitment": commitment, "approved_by": approved_by})
	frappe.db.commit()
	return doc.as_dict()


def get_committed_total(cost_code: str) -> float:
	"""Read live - never a cached rollup field (ERD §3.1 design note)."""
	result = frappe.db.sql(
		"select coalesce(sum(revised_amount), 0) from `tabCommitment` "
		"where cost_code = %s and status = 'Approved'",
		cost_code,
	)
	return float(result[0][0]) if result else 0.0
