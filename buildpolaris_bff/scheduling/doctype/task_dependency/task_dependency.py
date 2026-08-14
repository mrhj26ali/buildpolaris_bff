import frappe
from frappe.model.document import Document

VALID_TYPES = {"FS", "SS", "FF", "SF"}


class TaskDependency(Document):
	def validate(self):
		if self.type not in VALID_TYPES:
			frappe.throw(f"type must be one of {VALID_TYPES}.")
		if self.predecessor == self.successor:
			frappe.throw("A task cannot depend on itself.")
