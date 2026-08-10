import frappe
from frappe.tests.utils import FrappeTestCase
from buildpolaris_bff.project_closeout.services import gates, documents
from buildpolaris_bff.field_execution.services import punch_list
import uuid

class TestProjectCloseout(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        companies = frappe.get_all("Company", pluck="name")
        cls.company = companies[0] if companies else "HIAST"
        cls.proj_name = f"TEST-CLOSE-{uuid.uuid4().hex[:6]}"
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
        frappe.db.delete("Consent Of Surety", {"project": cls.project_id})
        frappe.db.delete("Lien Waiver", {"project": cls.project_id})
        frappe.db.delete("Contractors Affidavit", {"project": cls.project_id})
        frappe.db.delete("OM Manual", {"project": cls.project_id})
        frappe.db.delete("Warranty Document", {"project": cls.project_id})
        frappe.db.delete("Substantial Completion Certificate", {"project": cls.project_id})
        frappe.db.delete("Closing Record", {"project": cls.project_id})
        frappe.db.delete("Punch List Item", {"project": cls.project_id})
        frappe.db.delete("Project", cls.project_id)
        frappe.db.commit()
        super().tearDownClass()

    def test_closeout_initiation(self):
        closing_id = gates.initiate_closeout(project=self.project_id)
        closing = frappe.get_doc("Closing Record", closing_id)
        self.assertEqual(closing.status, "Initiated")
        self.assertIsNotNone(closing.initiated_at)

    def test_substantial_completion_with_open_punch_items(self):
        punch_list.create_punch_item(project=self.project_id, title="Touch up paint", priority="Low")
        punch_list.create_punch_item(project=self.project_id, title="Fix door hinge", priority="Medium")
        
        cert_id = gates.issue_substantial_completion(project=self.project_id, substantial_completion_date="2026-08-15", responsibility_terms="Utilities transfer to Owner on SC date.")
        cert = frappe.get_doc("Substantial Completion Certificate", cert_id)
        self.assertEqual(cert.status, "PendingSignature")
        self.assertIn("Touch up paint", cert.punch_snapshot)
        self.assertIn("Fix door hinge", cert.punch_snapshot)
        self.assertEqual(str(cert.warranty_start_date), "2026-08-15")

    def test_substantial_completion_signatures_immutable(self):
        cert_id = gates.issue_substantial_completion(project=self.project_id, substantial_completion_date="2026-08-15")
        
        gates.sign_substantial_completion(cert_id, signer_role="Owner", signer_user=self.test_user)
        cert = frappe.get_doc("Substantial Completion Certificate", cert_id)
        self.assertIsNotNone(cert.owner_signed_at)
        self.assertEqual(cert.status, "PendingSignature")
        
        with self.assertRaises(frappe.exceptions.ValidationError):
            gates.sign_substantial_completion(cert_id, signer_role="Owner", signer_user=self.test_user)
            
        gates.sign_substantial_completion(cert_id, signer_role="Architect", signer_user=self.test_user)
        cert.reload()
        self.assertEqual(cert.status, "Signed")

    def test_final_completion_gate_blocks_with_open_punch(self):
        punch_list.create_punch_item(project=self.project_id, title="Gate blocker 1", priority="High")
        punch_list.create_punch_item(project=self.project_id, title="Gate blocker 2", priority="Low")
        
        result = gates.check_final_completion_gate(self.project_id)
        self.assertFalse(result["cleared"])
        self.assertGreater(result["open_count"], 0)

    def test_final_completion_gate_passes_when_all_closed(self):
        open_items = frappe.get_all("Punch List Item", filters={"project": self.project_id, "status": ["!=", "Closed"]}, pluck="name")
        for item_id in open_items:
            punch_list.close_punch_item(item_id)
            
        result = gates.check_final_completion_gate(self.project_id)
        self.assertTrue(result["cleared"])
        self.assertEqual(result["open_count"], 0)

    def test_warranty_start_date_from_certificate(self):
        warranty_id = documents.create_warranty_document(project=self.project_id, supplier="HVAC Corp", system_scope="HVAC System", warranty_term_months=24)
        warranty = frappe.get_doc("Warranty Document", warranty_id)
        self.assertEqual(str(warranty.warranty_start_date), "2026-08-15")

    def test_retainage_release_gates(self):
        with self.assertRaises(frappe.exceptions.ValidationError):
            gates.release_final_retainage(self.project_id)
            
        documents.create_affidavit(project=self.project_id, supplier="GC Inc", all_debts_satisfied=1)
        with self.assertRaises(frappe.exceptions.ValidationError):
            gates.release_final_retainage(self.project_id)
            
        documents.create_lien_waiver(project=self.project_id, supplier="GC Inc", is_final=1)
        result = gates.release_final_retainage(self.project_id)
        self.assertEqual(result["status"], "success")
        
        closing = frappe.get_doc("Closing Record", result["closing_record"])
        self.assertEqual(closing.status, "FinalComplete")
        self.assertIsNotNone(closing.completed_at)

    def test_consent_of_surety_conditional(self):
        proj_name = f"TEST-BOND-{uuid.uuid4().hex[:6]}"
        proj_doc = frappe.get_doc({"doctype": "Project", "project_name": proj_name, "status": "Open", "company": self.company}).insert(ignore_permissions=True)
        bonded_project_id = proj_doc.name
        try:
            gates.initiate_closeout(project=bonded_project_id, project_has_payment_bond=1)
            consent_id = documents.create_consent_of_surety(project=bonded_project_id, surety_name="National Surety Co")
            consent = frappe.get_doc("Consent Of Surety", consent_id)
            self.assertEqual(consent.surety_name, "National Surety Co")
        finally:
            frappe.db.delete("Consent Of Surety", {"project": bonded_project_id})
            frappe.db.delete("Closing Record", {"project": bonded_project_id})
            frappe.db.delete("Project", bonded_project_id)

    def test_consent_of_surety_rejected_for_unbonded(self):
        with self.assertRaises(frappe.exceptions.ValidationError):
            documents.create_consent_of_surety(project=self.project_id, surety_name="Fake Surety")

    def test_security_project_isolation(self):
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc({"doctype": "Closing Record", "status": "Initiated"}).insert(ignore_permissions=True)