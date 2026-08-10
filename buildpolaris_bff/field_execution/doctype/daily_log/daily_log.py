import frappe
from frappe.model.document import Document


class DailyLog(Document):
    def validate(self):
        if self.log_date:
            from frappe.utils import today
            if str(self.log_date) > today():
                frappe.throw("Log date cannot be in the future")

    def before_save(self):
        if not self.submitted_by:
            self.submitted_by = frappe.session.user

    def on_update(self):
        if self.has_value_changed("status") and self.status == "Submitted":
            frappe.get_doc(
                {
                    "doctype": "Escalation Log",
                    "reference_doctype": "Daily Log",
                    "reference_name": self.name,
                    "escalation_tier": 0,
                    "escalated_at": frappe.utils.now_datetime(),
                }
            ).insert(ignore_permissions=True)
