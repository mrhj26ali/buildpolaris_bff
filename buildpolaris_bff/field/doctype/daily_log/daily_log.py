import frappe
from frappe.model.document import Document


class DailyLog(Document):
	def validate(self):
		if not self.submitted_by:
			self.submitted_by = frappe.session.user
