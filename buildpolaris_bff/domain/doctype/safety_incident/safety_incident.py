import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class SafetyIncident(Document):
    def validate(self):
        if self.incident_type in ("Recordable", "Lost Time", "Fatality"):
            self.osha_recordable = 1
        elif self.incident_type in ("Near Miss", "First Aid"):
            self.osha_recordable = 0

        severity_map = {
            "Near Miss": "Low",
            "First Aid": "Moderate",
            "Recordable": "Serious",
            "Lost Time": "Critical",
            "Fatality": "Fatal",
        }
        if self.incident_type:
            self.severity = severity_map.get(self.incident_type, "Low")

    def before_save(self):
        if not self.reported_by:
            self.reported_by = frappe.session.user

    def on_update(self):
        if self.has_value_changed("status"):
            frappe.get_doc(
                {
                    "doctype": "Escalation Log",
                    "reference_doctype": "Safety Incident",
                    "reference_name": self.name,
                    "escalation_tier": 0,
                    "escalated_at": now_datetime(),
                }
            ).insert(ignore_permissions=True)
