import frappe
from frappe.tests.utils import FrappeTestCase
from buildpolaris_bff.financials.services import budget, commitment, change_event, pay_application
import uuid

class TestFinancialControl(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        companies = frappe.get_all("Company", pluck="name")
        cls.company = companies[0] if companies else "HIAST"
        cls.proj_name = f"TEST-FIN-{uuid.uuid4().hex[:6]}"
        proj_doc = frappe.get_doc({
            "doctype": "Project",
            "project_name": cls.proj_name,
            "status": "Open",
            "company": cls.company,
        }).insert(ignore_permissions=True)
        cls.project_id = proj_doc.name
        cls.test_user = "Administrator"

    @classmethod
    def tearDownClass(cls):
        frappe.db.delete("Pay Application Line", {"parent": ["in", frappe.get_all("Pay Application", filters={"project": cls.project_id}, pluck="name")]})
        frappe.db.delete("Pay Application", {"project": cls.project_id})
        frappe.db.delete("Change Event", {"project": cls.project_id})
        frappe.db.delete("Commitment", {"project": cls.project_id})
        frappe.db.delete("Cost Code", {"project": cls.project_id})
        frappe.db.delete("Project", cls.project_id)
        frappe.db.commit()
        super().tearDownClass()

    def test_cost_code_creation(self):
        cc_id = budget.create_cost_code(project=self.project_id, code="03 30 00", title="Cast-in-Place Concrete", original_budget=150000)
        cc = frappe.get_doc("Cost Code", cc_id)
        self.assertEqual(cc.code, "03 30 00")
        self.assertEqual(cc.original_budget, 150000)
        self.assertEqual(cc.revised_budget, 150000)

    def test_commitment_lifecycle(self):
        cc_id = budget.create_cost_code(project=self.project_id, code="05 12 00", title="Structural Steel", original_budget=200000)
        com_id = commitment.create_commitment(project=self.project_id, cost_code=cc_id, vendor="Steel Fabricators Inc", original_amount=180000)
        com = frappe.get_doc("Commitment", com_id)
        self.assertEqual(com.status, "Draft")
        commitment.approve_commitment(com_id)
        com.reload()
        self.assertEqual(com.status, "Approved")
        cc = frappe.get_doc("Cost Code", cc_id)
        self.assertEqual(cc.committed_amount, 180000)

    def test_change_event_approval_updates_commitment(self):
        cc_id = budget.create_cost_code(project=self.project_id, code="09 29 00", title="Gypsum Board", original_budget=50000)
        com_id = commitment.create_commitment(project=self.project_id, cost_code=cc_id, vendor="Drywall Co", original_amount=45000)
        commitment.approve_commitment(com_id)
        
        ce_id = change_event.create_change_event(project=self.project_id, title="Additional drywall for Level 2", amount=5000, linked_commitment=com_id, cost_code=cc_id)
        change_event.submit_change_event(ce_id)
        change_event.approve_change_event(ce_id, approved_by=self.test_user)
        
        ce = frappe.get_doc("Change Event", ce_id)
        self.assertEqual(ce.status, "Approved")
        self.assertIsNotNone(ce.approved_at)
        com = frappe.get_doc("Commitment", com_id)
        self.assertEqual(com.approved_changes, 5000)
        self.assertEqual(com.revised_amount, 50000)

    def test_change_event_workflow_gates(self):
        ce_id = change_event.create_change_event(project=self.project_id, title="Gate test change", amount=1000)
        with self.assertRaises(frappe.exceptions.ValidationError):
            change_event.approve_change_event(ce_id)

    def test_pay_application_calculation(self):
        cc_id = budget.create_cost_code(project=self.project_id, code="14 21 00", title="Elevators", original_budget=100000)
        com_id = commitment.create_commitment(project=self.project_id, cost_code=cc_id, vendor="Elevator Corp", original_amount=95000, retainage_percent=10)
        commitment.approve_commitment(com_id)
        
        pay_app_id = pay_application.create_pay_application(
            project=self.project_id, commitment_id=com_id, period_start="2026-08-01", period_end="2026-08-31",
            lines=[
                {"description": "Elevator installation", "scheduled_value": 95000, "previous_completed": 0, "current_completed": 30000},
                {"description": "Controls wiring", "scheduled_value": 0, "previous_completed": 0, "current_completed": 5000},
            ],
        )
        pay_app = frappe.get_doc("Pay Application", pay_app_id)
        self.assertEqual(pay_app.total_completed, 35000)
        self.assertEqual(pay_app.retainage_amount, 3500)
        self.assertEqual(pay_app.net_due, 31500)

    def test_pay_application_workflow(self):
        cc_id = budget.create_cost_code(project=self.project_id, code="23 00 00", title="HVAC", original_budget=80000)
        com_id = commitment.create_commitment(project=self.project_id, cost_code=cc_id, vendor="HVAC Systems", original_amount=75000)
        commitment.approve_commitment(com_id)
        
        pay_app_id = pay_application.create_pay_application(project=self.project_id, commitment_id=com_id, lines=[{"description": "Ductwork", "scheduled_value": 75000, "previous_completed": 0, "current_completed": 20000}])
        pay_app = frappe.get_doc("Pay Application", pay_app_id)
        self.assertEqual(pay_app.status, "Draft")
        
        pay_application.submit_pay_application(pay_app_id)
        pay_app.reload()
        self.assertEqual(pay_app.status, "Submitted")
        
        pay_application.approve_pay_application(pay_app_id)
        pay_app.reload()
        self.assertEqual(pay_app.status, "Approved")

    def test_security_project_isolation(self):
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc({"doctype": "Cost Code", "code": "99 99 99", "title": "Orphan Code"}).insert(ignore_permissions=True)