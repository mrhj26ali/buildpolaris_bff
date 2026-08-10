import datetime
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from buildpolaris_bff.identity.api import users as users_api
from buildpolaris_bff.identity.services import identity as svc
from buildpolaris_bff.install import _bootstrap
from buildpolaris_bff.shared.crypto_utils import hash_token
from buildpolaris_bff.shared.rate_limit import is_rate_limited


TEST_PASSWORD = "Passw0rd!123"


def _u():
    return frappe.generate_hash(length=8)


class MockCache:
    """Simple in-memory cache mock for testing rate limiter independently of Redis."""
    def __init__(self):
        self.store = {}

    def get_value(self, key):
        return self.store.get(key)

    def set_value(self, key, value, expires_in_sec=None):
        self.store[key] = value


class TestIdentitySecurity(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        _bootstrap()

    def setUp(self):
        frappe.set_user("Administrator")

    def _register_admin(self):
        suffix = _u()
        company_name = f"SecCo {suffix}"
        email = f"sec-admin-{suffix}@example.com"

        result = svc.register_new_tenant(
            company_name=company_name,
            admin_email=email,
            admin_first_name="Sec Admin",
            password=TEST_PASSWORD,
        )

        return result, email, company_name

    def _activate_admin(self, result, email):
        token = result["activation_token"]
        response = svc.activate_account(token)
        self.assertEqual(response["status"], "activated")
        frappe.set_user(email)

    def test_activation_token_is_stored_hashed(self):
        result, email, _ = self._register_admin()
        raw_token = result["activation_token"]

        stored_value = frappe.db.get_value("User", email, "bp_activation_token")

        self.assertNotEqual(stored_value, raw_token)
        self.assertEqual(stored_value, hash_token(raw_token))

    def test_invalid_token_returns_invalid(self):
        response = svc.activate_account("invalid-token")
        self.assertEqual(response["status"], "invalid")

    def test_expired_token_returns_expired(self):
        result, email, _ = self._register_admin()
        raw_token = result["activation_token"]

        frappe.db.set_value(
            "User",
            email,
            "bp_activation_expiry",
            now_datetime() - datetime.timedelta(hours=1),
        )

        response = svc.activate_account(raw_token)
        self.assertEqual(response["status"], "expired")

    def test_rate_limiter_blocks_excess_attempts(self):
        action = f"test-rate-{_u()}"
        mock_cache = MockCache()

        # Patch both the cache and the security logger to isolate rate limit logic
        with patch("buildpolaris_bff.shared.rate_limit.frappe.cache", return_value=mock_cache), \
             patch("buildpolaris_bff.shared.rate_limit.log_security_event") as mock_log:
            
            self.assertFalse(is_rate_limited(action, limit=2, seconds=60))
            self.assertFalse(is_rate_limited(action, limit=2, seconds=60))
            self.assertTrue(is_rate_limited(action, limit=2, seconds=60))
            
            # Verify the security event was logged when limit was exceeded
            mock_log.assert_called_once_with(
                "RATE_LIMIT_EXCEEDED",
                {
                    "action": action,
                    "ip": "cli",
                    "limit": 2,
                    "window_seconds": 60,
                },
            )

    def test_guest_cannot_list_users(self):
        frappe.set_user("Guest")

        with self.assertRaises(Exception):
            users_api.list_users()

    def test_non_admin_cannot_list_users(self):
        result, admin_email, _ = self._register_admin()
        self._activate_admin(result, admin_email)

        member = f"sec-member-{_u()}@example.com"
        invite_result = svc.invite_user(
            email=member,
            full_name="Sec Member",
            roles=["BuildPolaris Project Manager"],
        )

        svc.activate_account(invite_result["invite_token"], TEST_PASSWORD)

        frappe.set_user(member)

        with self.assertRaises(Exception):
            users_api.list_users()

    def test_cross_company_user_update_is_blocked(self):
        result_a, admin_a, company_a = self._register_admin()
        self._activate_admin(result_a, admin_a)

        user_a = f"user-a-{_u()}@example.com"
        invite_a = svc.invite_user(
            email=user_a,
            full_name="User A",
            roles=["BuildPolaris Project Manager"],
        )
        svc.activate_account(invite_a["invite_token"], TEST_PASSWORD)

        result_b, admin_b, company_b = self._register_admin()
        self._activate_admin(result_b, admin_b)

        self.assertNotEqual(company_a, company_b)

        with self.assertRaises(Exception):
            svc.update_user_roles(
                email=user_a,
                roles=["BuildPolaris Site Superintendent"],
            )
