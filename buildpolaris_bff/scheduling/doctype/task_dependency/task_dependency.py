import frappe
from frappe.model.document import Document
from buildpolaris_bff.scheduling.services.cpm_engine import validate_acyclic_graph

class TaskDependency(Document):
    def validate(self):
        # FR-4: Dependency & Schedule Integrity Validation (Cycle Detection)
        validate_acyclic_graph(self.predecessor_task, self.successor_task)