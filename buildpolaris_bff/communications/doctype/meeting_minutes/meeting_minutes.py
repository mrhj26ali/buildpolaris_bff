import frappe
from frappe.model.document import Document


class MeetingMinutes(Document):
    def before_save(self):
        # FR-10: Auto-assign sequence number from series
        if self.series and not self.sequence_number:
            series = frappe.get_doc("Meeting Series", self.series)
            self.sequence_number = series.next_sequence_number()