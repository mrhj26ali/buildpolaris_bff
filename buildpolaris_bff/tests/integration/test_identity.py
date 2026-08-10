import unittest
import frappe
from buildpolaris_bff.identity.services import identity as svc
from buildpolaris_bff.shared import erpnext_bridge as bridge
from buildpolaris_bff.install import ADMIN_ROLE_NAME, _bootstrap

TEST_PASSWORD = "Passw0rd!123"

def _u():
    return frappe.generate_hash(length=8)

class TestModule1Identity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frappe.set_user("Administrator")
        _bootstrap()

    def setUp(self):
        frappe.set_user("Administrator")

    def test_register_creates_isolated_disabled_admin(self):
        suffix = _u()
        company_name = f"TestCo {suffix}"
        email = f"admin-{suffix}@example.com"
        res = svc.register_new_tenant(company_name, email, "Admin", TEST_PASSWORD)
        self.assertEqual(res["status"], "success")
        self.assertTrue(frappe.db.exists("Company", company_name))
        self.assertEqual(frappe.db.get_value("User", email, "enabled"), 0)
        self.assertIn(ADMIN_ROLE_NAME, frappe.get_roles(email))
        self.assertEqual(bridge.get_user_company(email), company_name)
        self.assertTrue(frappe.db.exists("User Permission", {"user": email, "allow": "Company", "for_value": company_name}))

    def test_duplicate_company_rejected(self):
        suffix = _u()
        svc.register_new_tenant(f"DupCo {suffix}", f"a1-{suffix}@example.com", "A", TEST_PASSWORD)
        with self.assertRaises(Exception):
            svc.register_new_tenant(f"DupCo {suffix}", f"a2-{suffix}@example.com", "B", TEST_PASSWORD)

    def test_activation_enables_admin(self):
        suffix = _u()
        email = f"act-{suffix}@example.com"
        svc.register_new_tenant(f"ActCo {suffix}", email, "A", TEST_PASSWORD)
        token = frappe.db.get_value("User", email, "bp_activation_token")
        self.assertTrue(token)
        self.assertEqual(svc.activate_account(token)["status"], "activated")
        self.assertEqual(frappe.db.get_value("User", email, "enabled"), 1)
        self.assertIsNone(frappe.db.get_value("User", email, "bp_activation_token"))

    def _make_admin(self):
        suffix = _u()
        email = f"boss-{suffix}@example.com"
        svc.register_new_tenant(f"BossCo {suffix}", email, "Boss", TEST_PASSWORD)
        token = frappe.db.get_value("User", email, "bp_activation_token")
        svc.activate_account(token)
        return email, bridge.get_user_company(email)

    def test_invite_assigns_roles_and_isolation(self):
        admin_email, company = self._make_admin()
        frappe.set_user(admin_email)
        invitee = f"inv-{_u()}@example.com"
        svc.invite_user(invitee, "Invitee", ["BuildPolaris Site Superintendent"])
        self.assertIn("BuildPolaris Site Superintendent", frappe.get_roles(invitee))
        self.assertEqual(bridge.get_user_company(invitee), company)
        self.assertTrue(frappe.db.exists("User Permission", {"user": invitee, "allow": "Company", "for_value": company}))
        self.assertEqual(frappe.db.get_value("User", invitee, "bp_needs_password"), 1)

    def test_invitee_activation_requires_password(self):
        admin_email, _ = self._make_admin()
        frappe.set_user(admin_email)
        invitee = f"inv2-{_u()}@example.com"
        svc.invite_user(invitee, "Invitee", ["BuildPolaris Subcontractor"])
        token = frappe.db.get_value("User", invitee, "bp_invite_token")
        self.assertEqual(svc.activate_account(token)["status"], "password_required")
        self.assertEqual(svc.activate_account(token, TEST_PASSWORD)["status"], "activated")
        self.assertEqual(frappe.db.get_value("User", invitee, "bp_invite_status"), "Accepted")

    def test_last_admin_cannot_be_demoted(self):
        admin_email, _ = self._make_admin()
        frappe.set_user(admin_email)
        with self.assertRaises(Exception):
            svc.update_user_roles(admin_email, ["BuildPolaris Project Manager"])

    def test_non_admin_cannot_invite(self):
        admin_email, _ = self._make_admin()
        frappe.set_user(admin_email)
        member = f"m-{_u()}@example.com"
        svc.invite_user(member, "Member", ["BuildPolaris Project Manager"])
        token = frappe.db.get_value("User", member, "bp_invite_token")
        svc.activate_account(token, TEST_PASSWORD)
        frappe.set_user(member)
        with self.assertRaises(Exception):
            svc.invite_user(f"x-{_u()}@example.com", "X", ["BuildPolaris Subcontractor"])

    def test_session_context_resolves_persona(self):
        admin_email, company = self._make_admin()
        frappe.set_user(admin_email)
        ctx = svc.get_session_context()
        self.assertEqual(ctx["persona"], "admin")
        self.assertEqual(ctx["company"], company)
        self.assertTrue(ctx["is_admin"])