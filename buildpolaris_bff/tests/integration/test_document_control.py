import frappe
from frappe.tests.utils import FrappeTestCase
from buildpolaris_bff.document_control.services import drawing, revision, annotation
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
            "status": "",
            "company": cls.company,
        }).insert(ignore_permissions=True)
        cls.project_id = proj_doc.name
        cls.test_user = "Administrator"

    @classmethod
    def tearDownClass(cls):
        revisions = frappe.get_all("Drawing Revision", filters={"project": cls.project_id}, pluck="name")
        if revisions:
            frappe.db.delete("Drawing Annotation", {"revision": ["in", revisions]})
            frappe.db.delete("Drawing Revision", {"project": cls.project_id})
            frappe.db.delete("Drawing", {"project": cls.project_id})
        frappe.db.delete("Project", cls.project_id)
        frappe.db.commit()
        super().tearDownClass()

    def test_drawing_creation(self):
        drawing_id = drawing.create_drawing(
            project=self.project_id,
            sheet_number="A-101",
            title="First Floor Plan",
            discipline="Architectural",
            classification_code="03 30 00",
        )
        drawing_doc = frappe.get_doc("Drawing", drawing_id)
        self.assertEqual(drawing_doc.sheet_number, "A-101")
        self.assertEqual(drawing_doc.status, "Active")
        self.assertEqual(drawing_doc.revision_count, 0)

    def test_revision_lifecycle_wip_to_shared(self):
        drawing_id = drawing.create_drawing(
            project=self.project_id,
            sheet_number="S-101",
            title="Foundation Plan",
            discipline="Structural",
        )
        rev_id = revision.create_revision(
            drawing_id=drawing_id,
            revision_code="A",
            native_file="/files/foundation.dwg",
            rendition_file="/files/foundation.pdf",
        )
        rev_doc = frappe.get_doc("Drawing Revision", rev_id)
        self.assertEqual(rev_doc.status, "WIP")
        self.assertEqual(rev_doc.status_code, "S0")
        revision.promote_to_shared(rev_id)
        rev_doc.reload()
        self.assertEqual(rev_doc.status, "Shared")
        self.assertEqual(rev_doc.status_code, "S1")

    def test_revision_lifecycle_full_publish(self):
        drawing_id = drawing.create_drawing(
            project=self.project_id,
            sheet_number="M-101",
            title="HVAC Layout",
            discipline="Mechanical",
        )
        rev_id = revision.create_revision(
            drawing_id=drawing_id,
            revision_code="A",
            rendition_file="/files/hvac.pdf",
        )
        revision.promote_to_shared(rev_id)
        revision.publish_revision(rev_id, authorized_by=self.test_user)
        rev_doc = frappe.get_doc("Drawing Revision", rev_id)
        self.assertEqual(rev_doc.status, "Published")
        self.assertEqual(rev_doc.status_code, "S2")
        self.assertIsNotNone(rev_doc.authorized_at)
        drawing_doc = frappe.get_doc("Drawing", drawing_id)
        self.assertEqual(drawing_doc.current_revision, rev_id)

    def test_revision_supersession(self):
        drawing_id = drawing.create_drawing(
            project=self.project_id,
            sheet_number="E-101",
            title="Electrical Panel Schedule",
            discipline="Electrical",
        )
        rev_a = revision.create_revision(drawing_id=drawing_id, revision_code="A")
        revision.promote_to_shared(rev_a)
        revision.publish_revision(rev_a)
        
        rev_b = revision.create_revision(drawing_id=drawing_id, revision_code="B")
        revision.promote_to_shared(rev_b)
        revision.publish_revision(rev_b)
        
        rev_a_doc = frappe.get_doc("Drawing Revision", rev_a)
        rev_b_doc = frappe.get_doc("Drawing Revision", rev_b)
        self.assertEqual(rev_a_doc.status, "Archived")
        self.assertEqual(rev_b_doc.status, "Published")
        drawing_doc = frappe.get_doc("Drawing", drawing_id)
        self.assertEqual(drawing_doc.current_revision, rev_b)

    def test_workflow_gate_cannot_publish_from_wip(self):
        drawing_id = drawing.create_drawing(
            project=self.project_id,
            sheet_number="P-101",
            title="Plumbing Riser",
            discipline="Plumbing",
        )
        rev_id = revision.create_revision(drawing_id=drawing_id, revision_code="A")
        with self.assertRaises(frappe.exceptions.ValidationError):
            revision.publish_revision(rev_id)

    def test_annotation_creation_and_conversion(self):
        drawing_id = drawing.create_drawing(
            project=self.project_id,
            sheet_number="A-201",
            title="Wall Sections",
            discipline="Architectural",
        )
        rev_id = revision.create_revision(drawing_id=drawing_id, revision_code="A")
        revision.promote_to_shared(rev_id)
        revision.publish_revision(rev_id)
        
        ann_id = annotation.create_annotation(
            revision_id=rev_id,
            annotation_type="Cloud",
            geometry='{"x": 100, "y": 200, "width": 50, "height": 30}',
            comment="Missing firestopping detail",
        )
        ann_doc = frappe.get_doc("Drawing Annotation", ann_id)
        self.assertEqual(ann_doc.annotation_type, "Cloud")
        self.assertIsNone(ann_doc.linked_punch_item)
        
        result = annotation.convert_annotation_to_punch_item(
            annotation_id=ann_id,
            title="Add firestopping detail",
            priority="High",
        )
        self.assertEqual(result["status"], "success")
        ann_doc.reload()
        self.assertIsNotNone(ann_doc.linked_punch_item)

    def test_security_project_isolation(self):
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc({
                "doctype": "Drawing",
                "sheet_number": "X-999",
                "title": "Orphan Drawing",
            }).insert(ignore_permissions=True)