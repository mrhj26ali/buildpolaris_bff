import frappe
from frappe.model.document import Document


class DrawingRevision(Document):
	def validate(self):
		self._guard_is_current()

	def _guard_is_current(self):
		"""FR-5.2: only the promotion endpoint may set is_current=1 - never
		a general update, enforced here so even a direct .save() can't
		bypass it ('enforced server-side, never a display-layer flag
		alone')."""
		if not self.is_current:
			return
		if self.flags.get("via_promotion"):
			return
		doc_before = self.get_doc_before_save()
		was_current = doc_before.is_current if doc_before else 0
		if not was_current:
			frappe.throw(
				"is_current can only be set via the revision-promotion "
				"endpoint (FR-5.2), never a direct field update."
			)
