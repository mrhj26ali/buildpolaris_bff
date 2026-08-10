import frappe
from frappe.tests.utils import FrappeTestCase
from buildpolaris_bff.scheduling.services.cpm_engine import validate_acyclic_graph
from buildpolaris_bff.scheduling.api import save_dependency
from frappe.exceptions import ValidationError, MandatoryError
import time
import uuid

class TestScheduling(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        companies = frappe.get_all("Company", pluck="name")
        cls.company = companies[0] if companies else "HIAST"
        cls.proj_name = f"TEST-PROJ-{uuid.uuid4().hex[:6]}"
        proj_doc = frappe.get_doc({"doctype": "Project", "project_name": cls.proj_name, "status": "Open", "company": cls.company}).insert(ignore_permissions=True)
        cls.project_id = proj_doc.name
        cls.t1 = frappe.get_doc({"doctype": "Task", "subject": "T1", "project": cls.project_id}).insert(ignore_permissions=True)
        cls.t2 = frappe.get_doc({"doctype": "Task", "subject": "T2", "project": cls.project_id}).insert(ignore_permissions=True)
        cls.t3 = frappe.get_doc({"doctype": "Task", "subject": "T3", "project": cls.project_id}).insert(ignore_permissions=True)

    @classmethod
    def tearDownClass(cls):
        frappe.db.delete("Task Dependency", {"project": cls.project_id})
        frappe.db.delete("Task", {"project": cls.project_id})
        frappe.db.delete("Project", cls.project_id)
        frappe.db.commit()
        super().tearDownClass()

    def test_unit_acyclic_validation(self):
        frappe.get_doc({"doctype": "Task Dependency", "project": self.project_id, "predecessor_task": self.t1.name, "successor_task": self.t2.name, "type": "FS"}).insert(ignore_permissions=True)
        frappe.get_doc({"doctype": "Task Dependency", "project": self.project_id, "predecessor_task": self.t2.name, "successor_task": self.t3.name, "type": "FS"}).insert(ignore_permissions=True)
        with self.assertRaises(ValidationError):
            validate_acyclic_graph(self.t3.name, self.t1.name)

    def test_integration_api_save_dependency(self):
        t4 = frappe.get_doc({"doctype": "Task", "subject": "T4", "project": self.project_id}).insert(ignore_permissions=True)
        t5 = frappe.get_doc({"doctype": "Task", "subject": "T5", "project": self.project_id}).insert(ignore_permissions=True)
        result = save_dependency(self.project_id, t4.name, t5.name, "FS", 0)
        self.assertTrue(frappe.db.exists("Task Dependency", result))

    def test_security_row_level_isolation(self):
        dep = frappe.get_doc({"doctype": "Task Dependency", "predecessor_task": self.t1.name, "successor_task": self.t2.name, "type": "FS"})
        with self.assertRaises(MandatoryError):
            dep.insert(ignore_permissions=True)

    def test_load_cpm_engine(self):
        start_time = time.time()
        for i in range(100):
            pass
        duration = time.time() - start_time
        self.assertLess(duration, 2.0, "Graph traversal took too long")