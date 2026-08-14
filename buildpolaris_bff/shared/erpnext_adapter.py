"""
Adapter over native ERPNext v16 doctypes - the ONLY path BuildPolaris uses
to touch financial data (REQ "Financial system of record" clause; no
parallel ledger, ever - ERD §3.1 design note).

financials/services/*.py (Phase 2, later) calls these functions; it never
constructs a Purchase Order / Purchase Invoice / Payment Entry doc directly,
so every financial-doctype creation path is auditable from one file.
"""
import frappe
from frappe.utils import flt, nowdate


def get_or_create_supplier(supplier_name: str, supplier_group: str | None = None) -> str:
	"""FR-3.2: Commitments reference a native Supplier - never a free-text
	vendor name. Reuses an existing Supplier by name."""
	existing = frappe.db.exists("Supplier", supplier_name)
	if existing:
		return existing

	doc = frappe.new_doc("Supplier")
	doc.supplier_name = supplier_name
	doc.supplier_group = supplier_group or _default_supplier_group()
	doc.supplier_type = "Company"
	doc.insert(ignore_permissions=True)
	return doc.name


def _default_supplier_group() -> str:
	group = frappe.db.get_single_value("Buying Settings", "supplier_group")
	return group or "All Supplier Groups"


def get_or_create_cost_center(company: str, cost_center_name: str | None = None) -> str:
	"""FR-3.1: optional Cost Code -> Cost Center cross-check link."""
	if not cost_center_name:
		return frappe.db.get_value("Company", company, "cost_center")

	existing = frappe.db.exists("Cost Center", {"cost_center_name": cost_center_name, "company": company})
	if existing:
		return existing

	doc = frappe.new_doc("Cost Center")
	doc.cost_center_name = cost_center_name
	doc.company = company
	doc.parent_cost_center = frappe.db.get_value("Company", company, "cost_center")
	doc.insert(ignore_permissions=True)
	return doc.name


def create_purchase_order(company: str, supplier: str, project: str, items: list[dict],
                           cost_center: str | None = None) -> str:
	"""FR-3.3: Commitment approval (PO-type only) creates and links a native
	Purchase Order. `items` is [{item_code|description, qty, rate}, ...]."""
	doc = frappe.new_doc("Purchase Order")
	doc.company = company
	doc.supplier = supplier
	doc.project = project
	doc.transaction_date = nowdate()
	for item in items:
		row = doc.append("items", {})
		row.item_code = item.get("item_code")
		row.item_name = item.get("description") or item.get("item_code")
		row.description = item.get("description")
		row.qty = flt(item.get("qty", 1))
		row.rate = flt(item.get("rate", 0))
		if cost_center:
			row.cost_center = cost_center
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def create_purchase_invoice_with_retainage(company: str, supplier: str, project: str,
                                            items: list[dict], retainage_pct: float,
                                            purchase_order: str | None = None) -> str:
	"""FR-3.5: Pay Application approval generates a native Purchase Invoice
	with retainage modeled as a held-back Payment Term - so it appears in
	ERPNext's own AP aging, never a side field the platform tracks alone."""
	doc = frappe.new_doc("Purchase Invoice")
	doc.company = company
	doc.supplier = supplier
	doc.project = project
	for item in items:
		row = doc.append("items", {})
		row.item_code = item.get("item_code")
		row.item_name = item.get("description") or item.get("item_code")
		row.description = item.get("description")
		row.qty = flt(item.get("qty", 1))
		row.rate = flt(item.get("rate", 0))
		if purchase_order:
			row.purchase_order = purchase_order

	if retainage_pct:
		_apply_retainage_payment_terms(doc, retainage_pct)

	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def _apply_retainage_payment_terms(purchase_invoice_doc, retainage_pct: float):
	"""Splits payment into an immediate-due portion and a retainage-held
	portion using ERPNext's native Payment Terms."""
	release_pct = 100 - flt(retainage_pct)
	purchase_invoice_doc.payment_terms_template = None
	purchase_invoice_doc.set("payment_schedule", [])
	purchase_invoice_doc.append("payment_schedule", {
		"payment_term": "Immediate",
		"invoice_portion": release_pct,
		"due_date": nowdate(),
	})
	purchase_invoice_doc.append("payment_schedule", {
		"payment_term": "Retainage Held",
		"invoice_portion": flt(retainage_pct),
		"due_date": nowdate(),
	})


def create_payment_entry(purchase_invoice: str, paid_amount: float | None = None) -> str:
	"""FR-3.5: payment against a Pay Application's Purchase Invoice creates
	a native Payment Entry linked back to it."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	pe = get_payment_entry("Purchase Invoice", purchase_invoice)
	if paid_amount is not None:
		pe.paid_amount = flt(paid_amount)
		pe.received_amount = flt(paid_amount)
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


def get_ap_aging_for_supplier(supplier: str, company: str) -> dict:
	"""Read AP figures live from ERPNext - never a duplicated total_paid /
	amount_outstanding field anywhere in BuildPolaris (ERD §3.1)."""
	rows = frappe.get_all(
		"Purchase Invoice",
		filters={"supplier": supplier, "company": company, "docstatus": 1},
		fields=["name", "grand_total", "outstanding_amount", "status"],
	)
	total_billed = sum(flt(r.grand_total) for r in rows)
	total_outstanding = sum(flt(r.outstanding_amount) for r in rows)
	return {
		"total_billed": total_billed,
		"total_outstanding": total_outstanding,
		"total_paid": total_billed - total_outstanding,
		"invoices": rows,
	}
