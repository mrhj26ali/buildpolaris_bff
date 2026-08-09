import frappe
from frappe.tests.utils import FrappeTestCase
from buildpolaris_bff.application import closeout_service as svc
from buildpolaris_bff.application import field_service
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
        """Unit Test: Closeout record is created with Initiated status."""
        closing_id = svc.initiate_closeout(project=self.project_id)
        closing = frappe.get_doc("Closing Record", closing_id)
        self.assertEqual(closing.status, "Initiated")
        self.assertIsNotNone(closing.initiated_at)

    def test_substantial_completion_with_open_punch_items(self):
        """Integration Test: S1 — SC is reached WITH punch items still open."""
        # Create some open punch items
        field_service.create_punch_item(
            project=self.project_id, title="Touch up paint", priority="Low"
        )
        field_service.create_punch_item(
            project=self.project_id, title="Fix door hinge", priority="Medium"
        )

        cert_id = svc.issue_substantial_completion(
            project=self.project_id,
            substantial_completion_date="2026-08-15",
            responsibility_terms="Utilities transfer to Owner on SC date.",
        )
        cert = frappe.get_doc("Substantial Completion Certificate", cert_id)

        # SC should be issued even with open punch items (S1)
        self.assertEqual(cert.status, "PendingSignature")
        self.assertIn("Touch up paint", cert.punch_snapshot)
        self.assertIn("Fix door hinge", cert.punch_snapshot)

        # Warranty start date should be the SC date
        self.assertEqual(str(cert.warranty_start_date), "2026-08-15")

    def test_substantial_completion_signatures_immutable(self):
        """Integration Test: NFR-4 — signatures are immutable once recorded."""
        cert_id = svc.issue_substantial_completion(
            project=self.project_id,
            substantial_completion_date="2026-08-15",
        )

        # Owner signs
        svc.sign_substantial_completion(cert_id, signer_role="Owner", signer_user=self.test_user)
        cert = frappe.get_doc("Substantial Completion Certificate", cert_id)
        self.assertIsNotNone(cert.owner_signed_at)
        self.assertEqual(cert.status, "PendingSignature")  # Still pending (Architect hasn't signed)

        # Try to sign again — should fail (immutable)
        with self.assertRaises(frappe.exceptions.ValidationError):
            svc.sign_substantial_completion(cert_id, signer_role="Owner", signer_user=self.test_user)

        # Architect signs
        svc.sign_substantial_completion(cert_id, signer_role="Architect", signer_user=self.test_user)
        cert.reload()
        self.assertEqual(cert.status, "Signed")

    def test_final_completion_gate_blocks_with_open_punch(self):
        """Integration Test: FR-2 — Final Completion gate blocks when punch items are open."""
        # Create open punch items (self-contained, independent of test execution order)
        field_service.create_punch_item(
            project=self.project_id, title="Gate blocker 1", priority="High"
        )
        field_service.create_punch_item(
            project=self.project_id, title="Gate blocker 2", priority="Low"
        )

        result = svc.check_final_completion_gate(self.project_id)
        self.assertFalse(result["cleared"])
        self.assertGreater(result["open_count"], 0)

    def test_final_completion_gate_passes_when_all_closed(self):
        """Integration Test: FR-2 — Gate passes when all punch items are closed."""
        # Close all punch items
        open_items = frappe.get_all(
            "Punch List Item",
            filters={"project": self.project_id, "status": ["!=", "Closed"]},
            pluck="name",
        )
        for item_id in open_items:
            field_service.close_punch_item(item_id)

        result = svc.check_final_completion_gate(self.project_id)
        self.assertTrue(result["cleared"])
        self.assertEqual(result["open_count"], 0)

    def test_warranty_start_date_from_certificate(self):
        """Integration Test: FR-3 — warranty_start_date sourced from SC certificate."""
        warranty_id = svc.create_warranty_document(
            project=self.project_id,
            supplier="HVAC Corp",
            system_scope="HVAC System",
            warranty_term_months=24,
        )
        warranty = frappe.get_doc("Warranty Document", warranty_id)
        # Should be sourced from the SC certificate date (2026-08-15)
        self.assertEqual(str(warranty.warranty_start_date), "2026-08-15")

    def test_retainage_release_gates(self):
        """Integration Test: FR-8 — retainage release requires all gates cleared."""
        # Punch gate should already be cleared from previous test
        # But affidavit, waiver, and surety consent are missing

        with self.assertRaises(frappe.exceptions.ValidationError):
            svc.release_final_retainage(self.project_id)

        # Add affidavit
        svc.create_affidavit(project=self.project_id, supplier="GC Inc", all_debts_satisfied=1)

        # Still should fail (no final waiver)
        with self.assertRaises(frappe.exceptions.ValidationError):
            svc.release_final_retainage(self.project_id)

        # Add final lien waiver
        svc.create_lien_waiver(project=self.project_id, supplier="GC Inc", is_final=1)

        # Now should pass (project is not bonded, so no surety consent needed)
        result = svc.release_final_retainage(self.project_id)
        self.assertEqual(result["status"], "success")

        # Verify closing record is FinalComplete
        closing = frappe.get_doc("Closing Record", result["closing_record"])
        self.assertEqual(closing.status, "FinalComplete")
        self.assertIsNotNone(closing.completed_at)

    def test_consent_of_surety_conditional(self):
        """Integration Test: FR-7 — surety consent only required for bonded projects."""
        # Create a bonded project
        proj_name = f"TEST-BOND-{uuid.uuid4().hex[:6]}"
        proj_doc = frappe.get_doc({
            "doctype": "Project",
            "project_name": proj_name,
            "status": "Open",
            "company": self.company,
        }).insert(ignore_permissions=True)
        bonded_project_id = proj_doc.name

        try:
            svc.initiate_closeout(project=bonded_project_id, project_has_payment_bond=1)

            # Trying to create surety consent should work for bonded project
            consent_id = svc.create_consent_of_surety(
                project=bonded_project_id, surety_name="National Surety Co"
            )
            consent = frappe.get_doc("Consent Of Surety", consent_id)
            self.assertEqual(consent.surety_name, "National Surety Co")
        finally:
            # Clean up bonded project
            frappe.db.delete("Consent Of Surety", {"project": bonded_project_id})
            frappe.db.delete("Closing Record", {"project": bonded_project_id})
            frappe.db.delete("Project", bonded_project_id)

    def test_consent_of_surety_rejected_for_unbonded(self):
        """Integration Test: FR-7 — surety consent rejected for unbonded projects."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            svc.create_consent_of_surety(project=self.project_id, surety_name="Fake Surety")

    def test_security_project_isolation(self):
        """Security Test: Cannot create Closing Record without project."""
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc({
                "doctype": "Closing Record",
                "status": "Initiated",
            }).insert(ignore_permissions=True)
