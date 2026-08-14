import frappe
from frappe.model.document import Document


class JSA(Document):
	def validate(self):
		if not self.prepared_by:
			self.prepared_by = frappe.session.user
		if not self.hazards:
			frappe.throw("A JSA must enumerate at least one hazard and mitigation (FR-6.2).")
