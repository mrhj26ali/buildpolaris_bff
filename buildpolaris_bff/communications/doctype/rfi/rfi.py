import frappe
from frappe.model.document import Document


class RFI(Document):
	def validate(self):
		if self.status == "Answered" and not self.response:
			frappe.throw("An RFI cannot be marked Answered without a response.")
