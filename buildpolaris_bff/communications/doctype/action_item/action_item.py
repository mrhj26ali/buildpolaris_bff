import frappe
from frappe.model.document import Document


class ActionItem(Document):
    def on_update(self):
        if self.has_value_changed("status") and self.status == "Closed":
            self._log_closure()

    def _log_closure(self):
        frappe.get_doc(
            {
                "doctype": "Escalation Log",
                "reference_doctype": "Action Item",
                "reference_name": self.name,
                "escalation_tier": 0,
                "escalated_at": frappe.utils.now_datetime(),
            }
        ).insert(ignore_permissions=True)