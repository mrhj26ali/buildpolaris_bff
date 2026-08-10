import frappe
from frappe.tests.utils import FrappeTestCase
from buildpolaris_bff.scheduling.services.cpm_engine import calculate_cpm

class TestSchedulingCPM(FrappeTestCase):
    def test_cpm_forward_backward_pass(self):
        tasks = [
            {"id": "A", "duration": 3, "predecessors": []},
            {"id": "B", "duration": 5, "predecessors": ["A"]},
            {"id": "C", "duration": 2, "predecessors": ["A"]},
            {"id": "D", "duration": 4, "predecessors": ["B", "C"]}
        ]
        
        result = calculate_cpm(tasks, "2026-08-11")
        
        # Task A: ES=0, EF=3
        # Task B: ES=3, EF=8
        # Task C: ES=3, EF=5
        # Task D: ES=8, EF=12
        
        self.assertEqual(result["project_duration"], 12)
        self.assertIn("A", result["critical_path"])
        self.assertIn("B", result["critical_path"])
        self.assertIn("D", result["critical_path"])
        self.assertNotIn("C", result["critical_path"])
        
        # Check Task C float: LS should be 6, ES is 3, so float is 3
        task_c = next(t for t in result["tasks"] if t["id"] == "C")
        self.assertEqual(task_c["total_float"], 3)
        self.assertFalse(task_c["is_critical"])
        
    def test_cpm_empty_tasks(self):
        result = calculate_cpm([], "2026-08-11")
        self.assertEqual(result["project_duration"], 0)
        self.assertEqual(len(result["tasks"]), 0)
