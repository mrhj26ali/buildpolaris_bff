import frappe
from frappe.model.document import Document

IMMUTABLE_STATUSES = ("Approved", "Paid")
PROTECTED_FIELDS = ["commitment", "period_end", "retainage_pct"]


class PayApplication(Document):
	def validate(self):
		self._enforce_immutability()

	def _enforce_immutability(self):
		"""FR-3.8. Pay Application has no dedicated is_immutable field
		(ERD §3.1) - immutability is governed by status: once the PRIOR
		persisted state was Approved/Paid, protected fields freeze."""
		if self.is_new() or self.flags.get("via_amendment"):
			return
		doc_before = self.get_doc_before_save()
		if not doc_before or doc_before.status not in IMMUTABLE_STATUSES:
			return

		for f in PROTECTED_FIELDS:
			if self.get(f) != doc_before.get(f):
				frappe.throw(f"Cannot modify '{f}' on an Approved/Paid Pay Application (FR-3.8).")

		before_lines = [
			(r.cost_code, r.scheduled_value, r.work_completed_this_period, r.materials_stored)
			for r in (doc_before.lines or [])
		]
		after_lines = [
			(r.cost_code, r.scheduled_value, r.work_completed_this_period, r.materials_stored)
			for r in (self.lines or [])
		]
		if before_lines != after_lines:
			frappe.throw("Cannot modify line items on an Approved/Paid Pay Application (FR-3.8).")
