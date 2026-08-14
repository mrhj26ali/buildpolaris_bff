import frappe
from frappe.model.document import Document


class PunchListItem(Document):
	def validate(self):
		if self.status == "Closed" and not self.closed_at:
			from frappe.utils import now_datetime
			self.closed_at = now_datetime()
