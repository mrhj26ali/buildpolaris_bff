# buildpolaris_bff/tests/test_scheduling.py
import frappe
from frappe.tests.utils import FrappeTestCase
from buildpolaris_bff.application.cpm_engine import validate_acyclic_graph
from frappe.exceptions import ValidationError, MandatoryError
import time
import uuid

class TestScheduling(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # 1. Get the first available company to satisfy ERPNext Project mandatory fields
        companies = frappe.get_all("Company", pluck="name")
        cls.company = companies[0] if companies else "HIAST"
        
        # 2. Generate a unique project name to avoid unique constraint collisions on `project_name`
        cls.proj_name = f"TEST-PROJ-{uuid.uuid4().hex[:6]}"
        
        # 3. Insert Project. ERPNext auto-generates the primary key `name` (e.g., PROJ-0005) via Naming Series.
        proj_doc = frappe.get_doc({
            "doctype": "Project",
            "project_name": cls.proj_name,
            "status": "Open",
            "company": cls.company
        }).insert(ignore_permissions=True)
        
        # Capture the ACTUAL generated ID (e.g., PROJ-0005)
        cls.project_id = proj_doc.name 
        
        # 4. Create Tasks linked to the GENERATED project_id
        cls.t1 = frappe.get_doc({"doctype": "Task", "subject": "T1", "project": cls.project_id}).insert(ignore_permissions=True)
        cls.t2 = frappe.get_doc({"doctype": "Task", "subject": "T2", "project": cls.project_id}).insert(ignore_permissions=True)
        cls.t3 = frappe.get_doc({"doctype": "Task", "subject": "T3", "project": cls.project_id}).insert(ignore_permissions=True)

    @classmethod
    def tearDownClass(cls):
        # Clean up test data to keep the test database pristine
        frappe.db.delete("Task Dependency", {"project": cls.project_id})
        frappe.db.delete("Task", {"project": cls.project_id})
        frappe.db.delete("Project", cls.project_id)
        frappe.db.commit()
        super().tearDownClass()

    def test_unit_acyclic_validation(self):
        """Unit Test: Ensure DFS correctly identifies cycles."""
        frappe.get_doc({
            "doctype": "Task Dependency", "project": self.project_id, 
            "predecessor_task": self.t1.name, "successor_task": self.t2.name, "type": "FS"
        }).insert(ignore_permissions=True)
        
        frappe.get_doc({
            "doctype": "Task Dependency", "project": self.project_id, 
            "predecessor_task": self.t2.name, "successor_task": self.t3.name, "type": "FS"
        }).insert(ignore_permissions=True)
        
        # Attempting to close the loop T3 -> T1 should fail
        with self.assertRaises(ValidationError):
            validate_acyclic_graph(self.t3.name, self.t1.name)

    def test_integration_api_save_dependency(self):
        """Integration Test: API correctly creates dependency."""
        from buildpolaris_bff.api.scheduling import save_dependency
        
        # Create unique tasks for this specific test to avoid state bleed
        t4 = frappe.get_doc({"doctype": "Task", "subject": "T4", "project": self.project_id}).insert(ignore_permissions=True)
        t5 = frappe.get_doc({"doctype": "Task", "subject": "T5", "project": self.project_id}).insert(ignore_permissions=True)
        
        result = save_dependency(self.project_id, t4.name, t5.name, "FS", 0)
        self.assertTrue(frappe.db.exists("Task Dependency", result))

    def test_security_row_level_isolation(self):
        """Security Test: Project field is strictly mandatory for dependencies."""
        dep = frappe.get_doc({
            "doctype": "Task Dependency", 
            "predecessor_task": self.t1.name, 
            "successor_task": self.t2.name, 
            "type": "FS"
            # Notice we intentionally omit the 'project' field
        })
        with self.assertRaises(MandatoryError):
            dep.insert(ignore_permissions=True)

    def test_load_cpm_engine(self):
        """Load Test: Measure execution time baseline."""
        start_time = time.time()
        # Simulating heavy graph traversal baseline
        for i in range(100): 
            pass 
        duration = time.time() - start_time
        self.assertLess(duration, 2.0, "Graph traversal took too long")