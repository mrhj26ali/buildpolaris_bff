import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, get_datetime, today

from buildpolaris_bff.field_execution.services.sync import process_mutations
from buildpolaris_bff.shared.erpnext_bridge import create_company


class TestFieldSync(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

        suffix = frappe.generate_hash(length=8)

        self.company_name = f"Sync Co {suffix}"
        self.company_abbr = f"T{suffix[:4]}".upper()
        self.project_name = f"Sync Project {suffix}"

        existing_company = frappe.db.get_value(
            "Company",
            {"company_name": self.company_name},
            "name",
        )

        if existing_company:
            self.company = existing_company
        else:
            created_company = create_company(
                self.company_name,
                self.company_abbr,
                "United States",
                "USD",
            )
            self.company = getattr(created_company, "name", created_company)

        project_doc = frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": self.project_name,
                "company": self.company,
            }
        ).insert(ignore_permissions=True)

        # Important: Daily Log.project must store the Project document name,
        # not the human-readable project_name.
        self.project = project_doc.name

    def test_create_daily_log_via_sync(self):
        mutations = [
            {
                "local_id": "test-uuid-1",
                "doctype": "Daily Log",
                "action": "create",
                "data": {
                    "project": self.project,
                    "log_date": today(),
                },
            }
        ]

        result = process_mutations(mutations, 0)

        self.assertEqual(result.get("errors", []), [])
        self.assertEqual(len(result["applied"]), 1, result)
        self.assertEqual(result["applied"][0]["action"], "created")

        server_name = result["applied"][0]["server_name"]
        self.assertTrue(frappe.db.exists("Daily Log", server_name))

    def test_conflict_detection(self):
        doc = frappe.get_doc(
            {
                "doctype": "Daily Log",
                "project": self.project,
                "log_date": add_days(today(), -1),
            }
        ).insert(ignore_permissions=True)

        # Derive an older sync timestamp from the actual server document.
        doc_modified_dt = get_datetime(doc.modified)
        older_sync_timestamp = int(doc_modified_dt.timestamp() * 1000) - 5000

        mutations = [
            {
                "local_id": "test-uuid-2",
                "server_name": doc.name,
                "doctype": "Daily Log",
                "action": "update",
                "data": {
                    "project": self.project,
                },
            }
        ]

        result = process_mutations(mutations, older_sync_timestamp)

        self.assertEqual(result.get("errors", []), [])
        self.assertEqual(len(result["conflicts"]), 1, result)
        self.assertEqual(result["conflicts"][0]["server_name"], doc.name)
