import frappe
from frappe.model.document import Document


class Transmittal(Document):
	def validate(self):
		if not self.recipients:
			frappe.throw("A Transmittal must have at least one recipient.")
		if not self.documents:
			frappe.throw("A Transmittal must reference at least one document (FR-4.3).")
