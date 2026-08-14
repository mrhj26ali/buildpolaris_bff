import frappe
from frappe.model.document import Document


class DrawingAnnotation(Document):
	def validate(self):
		if not self.author:
			self.author = frappe.session.user
