import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class PunchListItem(Document):
    def validate(self):
        if self.has_value_changed("status"):
            if self.status == "Closed" and not self.closed_at:
                self.closed_at = now_datetime()
            elif self.status != "Closed":
                self.closed_at = None

    def on_update(self):
        if self.has_value_changed("status"):
            frappe.get_doc(
                {
                    "doctype": "Escalation Log",
                    "reference_doctype": "Punch List Item",
                    "reference_name": self.name,
                    "escalation_tier": 0,
                    "escalated_at": now_datetime(),
                }
            ).insert(ignore_permissions=True)
