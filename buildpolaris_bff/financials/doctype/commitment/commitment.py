import frappe
from frappe.model.document import Document

PROTECTED_FIELDS = ["cost_code", "supplier", "type", "original_amount", "revised_amount"]


class Commitment(Document):
	def validate(self):
		if not self.revised_amount:
			self.revised_amount = self.original_amount
		self._enforce_immutability()

	def _enforce_immutability(self):
		"""FR-3.8: once Approved, immutable except through the defined
		amendment flow (financials/services/change_event_service.py sets
		flags.via_amendment before touching revised_amount)."""
		if self.is_new() or not self.is_immutable:
			return
		if self.flags.get("via_amendment"):
			return
		doc_before = self.get_doc_before_save()
		if not doc_before:
			return
		for f in PROTECTED_FIELDS:
			if self.get(f) != doc_before.get(f):
				frappe.throw(
					f"Cannot modify '{f}' on an approved, immutable Commitment "
					f"outside the amendment flow (FR-3.8)."
				)
