import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class JSA(Document):
    def validate(self):
        if self.status == "Approved" and not self.hazards:
            frappe.throw("Cannot approve JSA without identifying hazards")

    def on_update(self):
        if self.has_value_changed("status") and self.status == "Approved":
            self.approved_at = now_datetime()
            if not self.approved_by:
                self.approved_by = frappe.session.user
