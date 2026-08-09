import frappe
from frappe.tests.utils import FrappeTestCase
from buildpolaris_bff.application import field_service
import uuid


class TestFieldExecution(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        companies = frappe.get_all("Company", pluck="name")
        cls.company = companies[0] if companies else "HIAST"
        cls.proj_name = f"TEST-FIELD-{uuid.uuid4().hex[:6]}"

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
        frappe.db.delete("Daily Log Photo", {
            "parent": ["in", frappe.get_all("Daily Log", filters={"project": cls.project_id}, pluck="name")]
        })
        frappe.db.delete("Daily Log", {"project": cls.project_id})
        frappe.db.delete("Punch List Item", {"project": cls.project_id})
        frappe.db.delete("Safety Incident", {"project": cls.project_id})
        frappe.db.delete("JSA Hazard", {
            "parent": ["in", frappe.get_all("JSA", filters={"project": cls.project_id}, pluck="name")]
        })
        frappe.db.delete("JSA", {"project": cls.project_id})
        frappe.db.delete("Escalation Log", {
            "reference_name": ["in",
                frappe.get_all("Daily Log", filters={"project": cls.project_id}, pluck="name") +
                frappe.get_all("Punch List Item", filters={"project": cls.project_id}, pluck="name") +
                frappe.get_all("Safety Incident", filters={"project": cls.project_id}, pluck="name")
            ]
        })
        frappe.db.delete("Project", cls.project_id)
        frappe.db.commit()
        super().tearDownClass()

    def test_daily_log_lifecycle(self):
        """Unit Test: Daily Log follows Draft -> Submitted lifecycle."""
        log_id = field_service.create_daily_log(
            project=self.project_id,
            log_date="2026-08-08",
            weather_conditions="Sunny",
            workforce_count=12,
            work_performed="Poured concrete for foundation",
        )
        log = frappe.get_doc("Daily Log", log_id)
        self.assertEqual(log.status, "Draft")

        field_service.submit_daily_log(log_id)
        log.reload()
        self.assertEqual(log.status, "Submitted")

    def test_daily_log_with_photos(self):
        """Unit Test: Daily Log supports photo evidence with GPS."""
        log_id = field_service.create_daily_log(
            project=self.project_id,
            log_date="2026-08-08",
            photos=[
                {"file_url": "/files/photo1.jpg", "caption": "Foundation", "gps_lat": 33.5138, "gps_lng": 36.2765},
                {"file_url": "/files/photo2.jpg", "caption": "Rebar", "gps_lat": 33.5139, "gps_lng": 36.2766},
            ],
        )
        log = frappe.get_doc("Daily Log", log_id)
        self.assertEqual(len(log.photos), 2)
        self.assertEqual(log.photos[0].caption, "Foundation")

    def test_punch_item_lifecycle(self):
        """Unit Test: Punch List Item follows Open -> Closed lifecycle."""
        item_id = field_service.create_punch_item(
            project=self.project_id,
            title="Fix cracked tile in lobby",
            location="Main Lobby - Floor 1",
            priority="High",
        )
        item = frappe.get_doc("Punch List Item", item_id)
        self.assertEqual(item.status, "Open")
        self.assertIsNone(item.closed_at)

        field_service.close_punch_item(item_id, notes="Replaced tile")
        item.reload()
        self.assertEqual(item.status, "Closed")
        self.assertIsNotNone(item.closed_at)

    def test_punch_closeout_gate(self):
        """Integration Test: UC-29 closeout gate blocks when items are open."""
        field_service.create_punch_item(
            project=self.project_id,
            title="Gate test item",
            priority="Medium",
        )
        gate_result = field_service.check_punch_closeout_gate(self.project_id)
        self.assertFalse(gate_result["cleared"])
        self.assertGreater(gate_result["open_count"], 0)

    def test_safety_incident_osha_auto_flag(self):
        """Unit Test: OSHA recordable flag auto-sets based on incident type."""
        incident_id = field_service.create_safety_incident(
            project=self.project_id,
            incident_date="2026-08-08 14:30:00",
            incident_type="Lost Time",
            description="Worker fell from scaffold",
            injured_party="John Doe",
            employer="SubContractor Inc",
        )
        incident = frappe.get_doc("Safety Incident", incident_id)
        self.assertEqual(incident.osha_recordable, 1)
        self.assertEqual(incident.severity, "Critical")

        field_service.report_safety_incident(incident_id)
        incident.reload()
        self.assertEqual(incident.status, "Reported")

    def test_jsa_approval_requires_hazards(self):
        """Unit Test: JSA cannot be approved without hazards."""
        jsa_id = field_service.create_jsa(
            project=self.project_id,
            title="Excavation JSA",
            task_description="Excavation for foundation",
            hazards=[],
        )
        with self.assertRaises(frappe.exceptions.ValidationError):
            field_service.approve_jsa(jsa_id)

    def test_jsa_approval_with_hazards(self):
        """Unit Test: JSA can be approved with hazards identified."""
        jsa_id = field_service.create_jsa(
            project=self.project_id,
            title="Scaffold JSA",
            task_description="Scaffold erection for facade work",
            hazards=[
                {"hazard_description": "Fall from height", "risk_level": "High", "control_measure": "Harness required"},
                {"hazard_description": "Dropping tools", "risk_level": "Medium", "control_measure": "Tool lanyards"},
            ],
        )
        result = field_service.approve_jsa(jsa_id)
        self.assertEqual(result["status"], "success")

        jsa = frappe.get_doc("JSA", jsa_id)
        self.assertEqual(jsa.status, "Approved")
        self.assertIsNotNone(jsa.approved_at)

    def test_security_project_isolation(self):
        """Security Test: Cannot create Daily Log without project."""
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc({
                "doctype": "Daily Log",
                "log_date": "2026-08-08",
            }).insert(ignore_permissions=True)
