import frappe
from frappe.tests.utils import FrappeTestCase
from buildpolaris_bff.application import document_control_service as svc
import uuid


class TestDocumentControl(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        companies = frappe.get_all("Company", pluck="name")
        cls.company = companies[0] if companies else "HIAST"
        cls.proj_name = f"TEST-DOCS-{uuid.uuid4().hex[:6]}"

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
        # Clean up annotations
        revisions = frappe.get_all("Drawing Revision", filters={"project": cls.project_id}, pluck="name")
        if revisions:
            frappe.db.delete("Drawing Annotation", {"revision": ["in", revisions]})
        frappe.db.delete("Drawing Revision", {"project": cls.project_id})
        frappe.db.delete("Drawing", {"project": cls.project_id})
        frappe.db.delete("Project", cls.project_id)
        frappe.db.commit()
        super().tearDownClass()

    def test_drawing_creation(self):
        """Unit Test: Drawing is created with correct fields."""
        drawing_id = svc.create_drawing(
            project=self.project_id,
            sheet_number="A-101",
            title="First Floor Plan",
            discipline="Architectural",
            classification_code="03 30 00",
        )
        drawing = frappe.get_doc("Drawing", drawing_id)
        self.assertEqual(drawing.sheet_number, "A-101")
        self.assertEqual(drawing.status, "Active")
        self.assertEqual(drawing.revision_count, 0)

    def test_revision_lifecycle_wip_to_shared(self):
        """Unit Test: Revision follows WIP -> Shared lifecycle."""
        drawing_id = svc.create_drawing(
            project=self.project_id,
            sheet_number="S-101",
            title="Foundation Plan",
            discipline="Structural",
        )
        rev_id = svc.create_revision(
            drawing_id=drawing_id,
            revision_code="A",
            native_file="/files/foundation.dwg",
            rendition_file="/files/foundation.pdf",
        )
        rev = frappe.get_doc("Drawing Revision", rev_id)
        self.assertEqual(rev.status, "WIP")
        self.assertEqual(rev.status_code, "S0")

        svc.promote_to_shared(rev_id)
        rev.reload()
        self.assertEqual(rev.status, "Shared")
        self.assertEqual(rev.status_code, "S1")

    def test_revision_lifecycle_full_publish(self):
        """Integration Test: Full lifecycle WIP -> Shared -> Published."""
        drawing_id = svc.create_drawing(
            project=self.project_id,
            sheet_number="M-101",
            title="HVAC Layout",
            discipline="Mechanical",
        )
        rev_id = svc.create_revision(
            drawing_id=drawing_id,
            revision_code="A",
            rendition_file="/files/hvac.pdf",
        )
        svc.promote_to_shared(rev_id)
        svc.publish_revision(rev_id, authorized_by=self.test_user)

        rev = frappe.get_doc("Drawing Revision", rev_id)
        self.assertEqual(rev.status, "Published")
        self.assertEqual(rev.status_code, "S2")
        self.assertIsNotNone(rev.authorized_at)

        # Drawing should point to this revision
        drawing = frappe.get_doc("Drawing", drawing_id)
        self.assertEqual(drawing.current_revision, rev_id)

    def test_revision_supersession(self):
        """Integration Test: FR-4 — publishing new revision archives the old one."""
        drawing_id = svc.create_drawing(
            project=self.project_id,
            sheet_number="E-101",
            title="Electrical Panel Schedule",
            discipline="Electrical",
        )
        # Publish revision A
        rev_a = svc.create_revision(drawing_id=drawing_id, revision_code="A")
        svc.promote_to_shared(rev_a)
        svc.publish_revision(rev_a)

        # Publish revision B — should archive A
        rev_b = svc.create_revision(drawing_id=drawing_id, revision_code="B")
        svc.promote_to_shared(rev_b)
        svc.publish_revision(rev_b)

        rev_a_doc = frappe.get_doc("Drawing Revision", rev_a)
        rev_b_doc = frappe.get_doc("Drawing Revision", rev_b)

        self.assertEqual(rev_a_doc.status, "Archived")
        self.assertEqual(rev_b_doc.status, "Published")

        # Drawing should now point to B
        drawing = frappe.get_doc("Drawing", drawing_id)
        self.assertEqual(drawing.current_revision, rev_b)

    def test_workflow_gate_cannot_publish_from_wip(self):
        """Security Test: Cannot skip Shared step — WIP cannot go directly to Published."""
        drawing_id = svc.create_drawing(
            project=self.project_id,
            sheet_number="P-101",
            title="Plumbing Riser",
            discipline="Plumbing",
        )
        rev_id = svc.create_revision(drawing_id=drawing_id, revision_code="A")

        with self.assertRaises(frappe.exceptions.ValidationError):
            svc.publish_revision(rev_id)

    def test_annotation_creation_and_conversion(self):
        """Integration Test: Annotation creation and conversion to Punch Item."""
        drawing_id = svc.create_drawing(
            project=self.project_id,
            sheet_number="A-201",
            title="Wall Sections",
            discipline="Architectural",
        )
        rev_id = svc.create_revision(drawing_id=drawing_id, revision_code="A")
        svc.promote_to_shared(rev_id)
        svc.publish_revision(rev_id)

        ann_id = svc.create_annotation(
            revision_id=rev_id,
            annotation_type="Cloud",
            geometry='{"x": 100, "y": 200, "width": 50, "height": 30}',
            comment="Missing firestopping detail",
        )
        ann = frappe.get_doc("Drawing Annotation", ann_id)
        self.assertEqual(ann.annotation_type, "Cloud")
        self.assertIsNone(ann.linked_punch_item)

        # Convert to punch item
        result = svc.convert_annotation_to_punch_item(
            annotation_id=ann_id,
            title="Add firestopping detail",
            priority="High",
        )
        self.assertEqual(result["status"], "success")

        ann.reload()
        self.assertIsNotNone(ann.linked_punch_item)

    def test_security_project_isolation(self):
        """Security Test: Cannot create Drawing without project."""
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc({
                "doctype": "Drawing",
                "sheet_number": "X-999",
                "title": "Orphan Drawing",
            }).insert(ignore_permissions=True)
