import frappe
from frappe.model.document import Document


class SafetyIncident(Document):
	def validate(self):
		if not self.reported_by:
			self.reported_by = frappe.session.user
