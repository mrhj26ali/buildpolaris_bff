import frappe
from frappe.model.document import Document


class ClosingRecord(Document):
	def validate(self):
		self._guard_finalize()

	def _guard_finalize(self):
		"""FR-7.5: status can only become 'Finalized' via the closeout-gate
		endpoint - never a direct field update, even from the Desk UI."""
		if self.status != "Finalized":
			return
		if self.flags.get("via_gate"):
			return
		doc_before = self.get_doc_before_save()
		was_finalized = bool(doc_before and doc_before.status == "Finalized")
		if not was_finalized:
			frappe.throw(
				"status can only become 'Finalized' via the closeout-gate "
				"endpoint (FR-7.5), which verifies every blocker first."
			)
