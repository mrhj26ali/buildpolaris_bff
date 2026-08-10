import datetime

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from buildpolaris_bff.identity.services import identity as svc
from buildpolaris_bff.install import ADMIN_ROLE_NAME, PLATFORM_ROLES, _bootstrap
from buildpolaris_bff.shared import erpnext_bridge as bridge
from buildpolaris_bff.shared.crypto_utils import hash_token


TEST_PASSWORD = "Passw0rd!123"


def _u():
    return frappe.generate_hash(length=8)


class TestModule1Identity(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        _bootstrap()

    def setUp(self):
        frappe.set_user("Administrator")

    def _register_admin(self):
        suffix = _u()
        company_name = f"TestCo {suffix}"
        email = f"admin-{suffix}@example.com"

        result = svc.register_new_tenant(
            company_name=company_name,
            admin_email=email,
            admin_first_name="Admin",
            password=TEST_PASSWORD,
        )

        return result, email, company_name

    def _activate_admin(self, result, email):
        token = result["activation_token"]
        response = svc.activate_account(token)
        self.assertEqual(response["status"], "activated")
        frappe.set_user(email)

    def test_register_creates_isolated_disabled_admin(self):
        result, email, company_name = self._register_admin()
        token = result["activation_token"]

        self.assertTrue(frappe.db.exists("Company", company_name))
        self.assertEqual(frappe.db.get_value("User", email, "enabled"), 0)
        self.assertIn(ADMIN_ROLE_NAME, frappe.get_roles(email))
        self.assertEqual(bridge.get_user_company(email), company_name)

        stored_hash = frappe.db.get_value("User", email, "bp_activation_token")
        self.assertNotEqual(stored_hash, token)
        self.assertEqual(stored_hash, hash_token(token))

        response = svc.activate_account(token)
        self.assertEqual(response["status"], "activated")
        self.assertEqual(frappe.db.get_value("User", email, "enabled"), 1)
        self.assertIsNone(frappe.db.get_value("User", email, "bp_activation_token"))

    def test_duplicate_company_rejected(self):
        suffix = _u()
        company_name = f"DupCo {suffix}"

        svc.register_new_tenant(
            company_name=company_name,
            admin_email=f"a1-{suffix}@example.com",
            admin_first_name="A",
            password=TEST_PASSWORD,
        )

        with self.assertRaises(Exception):
            svc.register_new_tenant(
                company_name=company_name,
                admin_email=f"a2-{suffix}@example.com",
                admin_first_name="B",
                password=TEST_PASSWORD,
            )

    def test_activation_expired(self):
        result, email, _ = self._register_admin()
        token = result["activation_token"]

        frappe.db.set_value(
            "User",
            email,
            "bp_activation_expiry",
            now_datetime() - datetime.timedelta(hours=1),
        )

        response = svc.activate_account(token)
        self.assertEqual(response["status"], "expired")

    def test_invite_assigns_roles_and_isolation(self):
        result, admin_email, company_name = self._register_admin()
        self._activate_admin(result, admin_email)

        invitee = f"inv-{_u()}@example.com"
        invite_result = svc.invite_user(
            email=invitee,
            full_name="Invitee",
            roles=["BuildPolaris Site Superintendent"],
        )

        self.assertIn("BuildPolaris Site Superintendent", frappe.get_roles(invitee))
        self.assertEqual(bridge.get_user_company(invitee), company_name)
        self.assertTrue(
            frappe.db.exists(
                "User Permission",
                {
                    "user": invitee,
                    "allow": "Company",
                    "for_value": company_name,
                },
            )
        )
        self.assertEqual(frappe.db.get_value("User", invitee, "bp_needs_password"), 1)
        self.assertIn("invite_token", invite_result)

    def test_invitee_activation_requires_password(self):
        result, admin_email, _ = self._register_admin()
        self._activate_admin(result, admin_email)

        invitee = f"inv2-{_u()}@example.com"
        invite_result = svc.invite_user(
            email=invitee,
            full_name="Invitee",
            roles=["BuildPolaris Subcontractor"],
        )

        token = invite_result["invite_token"]

        response = svc.activate_account(token)
        self.assertEqual(response["status"], "password_required")

        response = svc.activate_account(token, TEST_PASSWORD)
        self.assertEqual(response["status"], "activated")
        self.assertEqual(frappe.db.get_value("User", invitee, "bp_invite_status"), "Accepted")

    def test_resend_invite_invalidates_old_token(self):
        result, admin_email, _ = self._register_admin()
        self._activate_admin(result, admin_email)

        invitee = f"inv3-{_u()}@example.com"
        old_invite = svc.invite_user(
            email=invitee,
            full_name="Invitee",
            roles=["BuildPolaris Project Manager"],
        )

        old_token = old_invite["invite_token"]

        resend_result = svc.resend_invite(invitee)
        new_token = resend_result["invite_token"]

        old_response = svc.activate_account(old_token, TEST_PASSWORD)
        self.assertEqual(old_response["status"], "invalid")

        new_response = svc.activate_account(new_token, TEST_PASSWORD)
        self.assertEqual(new_response["status"], "activated")

    def test_last_admin_cannot_be_demoted(self):
        result, admin_email, _ = self._register_admin()
        self._activate_admin(result, admin_email)

        with self.assertRaises(Exception):
            svc.update_user_roles(admin_email, ["BuildPolaris Project Manager"])

    def test_non_admin_cannot_invite(self):
        result, admin_email, _ = self._register_admin()
        self._activate_admin(result, admin_email)

        member = f"m-{_u()}@example.com"
        invite_result = svc.invite_user(
            email=member,
            full_name="Member",
            roles=["BuildPolaris Project Manager"],
        )

        svc.activate_account(invite_result["invite_token"], TEST_PASSWORD)

        frappe.set_user(member)

        with self.assertRaises(Exception):
            svc.invite_user(
                email=f"x-{_u()}@example.com",
                full_name="X",
                roles=["BuildPolaris Subcontractor"],
            )

    def test_list_users_and_available_roles(self):
        result, admin_email, _ = self._register_admin()
        self._activate_admin(result, admin_email)

        roles = svc.available_roles()
        self.assertEqual(len(roles), len(PLATFORM_ROLES))

        users = svc.list_tenant_users()
        emails = [user["email"] for user in users]

        self.assertIn(admin_email, emails)

    def test_set_user_enabled(self):
        result, admin_email, _ = self._register_admin()
        self._activate_admin(result, admin_email)

        member = f"m2-{_u()}@example.com"
        invite_result = svc.invite_user(
            email=member,
            full_name="Member Two",
            roles=["BuildPolaris Project Manager"],
        )

        svc.activate_account(invite_result["invite_token"], TEST_PASSWORD)

        frappe.set_user(admin_email)
        svc.set_user_enabled(member, False)

        self.assertEqual(frappe.db.get_value("User", member, "enabled"), 0)

        with self.assertRaises(Exception):
            svc.set_user_enabled(admin_email, False)
