import frappe
from frappe.model.document import Document

PROTECTED_FIELDS = ["commitment", "category", "amount_delta"]


class ChangeEvent(Document):
	def validate(self):
		self._enforce_immutability()

	def _enforce_immutability(self):
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
					f"Cannot modify '{f}' on an approved/rejected, immutable "
					f"Change Event outside the amendment flow (FR-3.8)."
				)
