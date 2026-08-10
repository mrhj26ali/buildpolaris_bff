import frappe
from frappe.tests.utils import FrappeTestCase
from buildpolaris_bff.communications.services import rfi, submittal, transmittal, action_item
import uuid

class TestCommunications(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        companies = frappe.get_all("Company", pluck="name")
        cls.company = companies[0] if companies else "HIAST"
        cls.proj_name = f"TEST-COMMS-{uuid.uuid4().hex[:6]}"
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
        rfis = frappe.get_all("RFI", filters={"project": cls.project_id}, pluck="name")
        if rfis:
            frappe.db.delete("RFI Watcher", {"rfi": ["in", rfis]})
            frappe.db.delete("Route Step", {"reference_name": ["in", rfis], "reference_doctype": "RFI"})
            frappe.db.delete("Escalation Log", {"reference_name": ["in", rfis], "reference_doctype": "RFI"})
            frappe.db.delete("RFI", {"project": cls.project_id})
        submittals = frappe.get_all("Submittal Package", filters={"project": cls.project_id}, pluck="name")
        if submittals:
            frappe.db.delete("Route Step", {"reference_name": ["in", submittals], "reference_doctype": "Submittal Package"})
            frappe.db.delete("Escalation Log", {"reference_name": ["in", submittals], "reference_doctype": "Submittal Package"})
            frappe.db.delete("Submittal Item", {"parent": ["in", submittals]})
            frappe.db.delete("Submittal Package", {"project": cls.project_id})
        transmittals = frappe.get_all("Transmittal", filters={"project": cls.project_id}, pluck="name")
        if transmittals:
            frappe.db.delete("Transmittal Recipient", {"parent": ["in", transmittals]})
            frappe.db.delete("Transmittal", {"project": cls.project_id})
        series = frappe.get_all("Meeting Series", filters={"project": cls.project_id}, pluck="name")
        if series:
            frappe.db.delete("Meeting Minutes", {"series": ["in", series]})
            frappe.db.delete("Action Item", {"minutes": ["in", series]})
            frappe.db.delete("Meeting Series", {"project": cls.project_id})
            frappe.db.delete("Action Item", {"project": cls.project_id})
        frappe.db.delete("Project", cls.project_id)
        frappe.db.commit()
        super().tearDownClass()

    def test_rfi_lifecycle(self):
        rfi_id = rfi.create_rfi(project=self.project_id, subject="Test RFI", description="Test description")
        rfi_doc = frappe.get_doc("RFI", rfi_id)
        self.assertEqual(rfi_doc.status, "Draft")
        
        rfi.submit_rfi(rfi_id)
        rfi_doc.reload()
        self.assertEqual(rfi_doc.status, "Open")
        
        rfi.answer_rfi(rfi_id, "Test reply")
        rfi_doc.reload()
        self.assertEqual(rfi_doc.status, "Answered")
        
        rfi.close_rfi(rfi_id)
        rfi_doc.reload()
        self.assertEqual(rfi_doc.status, "Closed")

    def test_rfi_sequential_numbering(self):
        rfi1 = rfi.create_rfi(project=self.project_id, subject="RFI 1")
        rfi2 = rfi.create_rfi(project=self.project_id, subject="RFI 2")
        rfi1_doc = frappe.get_doc("RFI", rfi1)
        rfi2_doc = frappe.get_doc("RFI", rfi2)
        num1 = int(rfi1_doc.rfi_number.split("-")[-1])
        num2 = int(rfi2_doc.rfi_number.split("-")[-1])
        self.assertEqual(num2, num1 + 1)

    def test_unified_routing(self):
        rfi_id = rfi.create_rfi(project=self.project_id, subject="Route Test")
        rfi.submit_rfi(rfi_id)
        route_step_id = rfi.route_item(
            project=self.project_id,
            reference_doctype="RFI",
            reference_name=rfi_id,
            reviewer=self.test_user,
            decision="Forward",
        )
        self.assertTrue(frappe.db.exists("Route Step", route_step_id))
        rfi_doc = frappe.get_doc("RFI", rfi_id)
        self.assertEqual(rfi_doc.ball_in_court, self.test_user)

    def test_transmittal_acknowledgment(self):
        transmittal_id = transmittal.create_transmittal(
            project=self.project_id,
            purpose="Test Transmittal",
            transmission_method="Email",
            recipients=[self.test_user],
        )
        result = transmittal.acknowledge_transmittal(transmittal_id, self.test_user)
        self.assertEqual(result["status"], "success")
        with self.assertRaises(frappe.exceptions.ValidationError):
            transmittal.acknowledge_transmittal(transmittal_id, self.test_user)

    def test_security_project_isolation(self):
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc({"doctype": "RFI", "subject": "No Project RFI"}).insert(ignore_permissions=True)