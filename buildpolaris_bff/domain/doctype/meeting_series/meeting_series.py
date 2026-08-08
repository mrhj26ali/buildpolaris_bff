from frappe.model.document import Document


class MeetingSeries(Document):
    def next_sequence_number(self):
        self.last_sequence_number += 1
        self.save(ignore_permissions=True)
        return self.last_sequence_number