import frappe
from frappe.model.document import Document


class CostCode(Document):
	def validate(self):
		if self.budget_amount is not None and self.budget_amount < 0:
			frappe.throw("Budget amount cannot be negative.")
