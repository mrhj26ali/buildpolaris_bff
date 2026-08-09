import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class DrawingRevision(Document):
    def validate(self):
        # Auto-sync status_code with status
        status_code_map = {
            "WIP": "S0",
            "Shared": "S1",
            "Published": "S2",
            "Archived": "S2",
        }
        if self.status in status_code_map:
            self.status_code = status_code_map[self.status]

    def before_save(self):
        if not self.uploaded_by:
            self.uploaded_by = frappe.session.user
        if not self.uploaded_at:
            self.uploaded_at = now_datetime()
