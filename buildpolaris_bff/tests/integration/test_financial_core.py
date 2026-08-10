import frappe
from frappe.tests.utils import FrappeTestCase

from buildpolaris_bff.financials import api_core as api
from buildpolaris_bff.shared.erpnext_bridge import create_company


class TestFinancialCore(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

        suffix = frappe.generate_hash(length=8)

        self.company_name = f"Financial Co {suffix}"
        self.company_abbr = f"F{suffix[:4]}".upper()
        self.project_name = f"Financial Project {suffix}"
        self.cost_code = f"CC-{suffix[:5].upper()}"

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

        self.project = project_doc.name

    def test_financial_core_flow(self):
        cost_result = api.create_cost_code(
            project=self.project,
            code=self.cost_code,
            label="Concrete",
            description="Concrete scope",
        )

        self.assertTrue(cost_result["success"], cost_result)
        cost_name = cost_result["data"]["name"]

        commitment_result = api.create_commitment(
            project=self.project,
            cost_code=cost_name,
            amount=1000,
            supplier="Test Supplier",
            date="2026-08-01",
            description="Concrete commitment",
        )

        self.assertTrue(commitment_result["success"], commitment_result)
        commitment_name = commitment_result["data"]["name"]

        change_result = api.create_change_event(
            project=self.project,
            cost_code=cost_name,
            amount=250,
            description="Additional concrete scope",
        )

        self.assertTrue(change_result["success"], change_result)

        pay_result = api.create_pay_application(
            project=self.project,
            commitment=commitment_name,
            period_start="2026-08-01",
            period_end="2026-08-31",
            lines=[
                {
                    "cost_code": cost_name,
                    "amount": 500,
                    "description": "Progress billing for concrete",
                }
            ],
        )

        self.assertTrue(pay_result["success"], pay_result)
        self.assertEqual(pay_result["data"]["total"], 500.0)

        summary_result = api.get_budget_summary(project=self.project)

        self.assertTrue(summary_result["success"], summary_result)

        summary = summary_result["data"]

        self.assertEqual(summary["project"], self.project)
        self.assertEqual(summary["total_committed"], 1000.0)
        self.assertEqual(summary["total_change_events"], 250.0)
        self.assertEqual(summary["total_pay_applications"], 500.0)
        self.assertGreaterEqual(summary["projected_total"], 1000.0)

        cost_codes = api.list_cost_codes(project=self.project)
        self.assertTrue(cost_codes["success"], cost_codes)
        self.assertGreaterEqual(len(cost_codes["data"]), 1)

        commitments = api.list_commitments(project=self.project)
        self.assertTrue(commitments["success"], commitments)
        self.assertGreaterEqual(len(commitments["data"]), 1)

        change_events = api.list_change_events(project=self.project)
        self.assertTrue(change_events["success"], change_events)
        self.assertGreaterEqual(len(change_events["data"]), 1)

        pay_apps = api.list_pay_applications(project=self.project)
        self.assertTrue(pay_apps["success"], pay_apps)
        self.assertGreaterEqual(len(pay_apps["data"]), 1)
