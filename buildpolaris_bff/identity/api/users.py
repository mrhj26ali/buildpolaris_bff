import json

import frappe
from frappe import _

from buildpolaris_bff.identity.services import identity as svc
from buildpolaris_bff.install import ADMIN_ROLE_NAME
from buildpolaris_bff.shared.api_utils import handle_api_error, standard_response
from buildpolaris_bff.shared.guards import require_roles


def _roles(roles) -> list[str]:
    """
    Normalize roles payload.
    Accepts: list, JSON string list, single role string.
    """
    if roles is None:
        return []

    if isinstance(roles, str):
        try:
            roles = json.loads(roles)
        except json.JSONDecodeError:
            roles = [roles]

    if not isinstance(roles, list):
        frappe.throw(_("Roles must be a list"), frappe.ValidationError)

    return [str(role) for role in roles]


@frappe.whitelist()
@require_roles(ADMIN_ROLE_NAME)
def available_roles():
    """FR-1.8 — role catalog for the checkbox UI."""
    try:
        return standard_response(
            True,
            svc.available_roles(),
            _("Available roles retrieved"),
        )
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_roles(ADMIN_ROLE_NAME)
def list_users():
    """FR-1.7 — tenant user list."""
    try:
        return standard_response(
            True,
            svc.list_tenant_users(),
            _("Users retrieved"),
        )
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_roles(ADMIN_ROLE_NAME)
def invite_user(email: str, full_name: str, roles):
    """UC-02 / FR-1.3: Invite a user."""
    try:
        result = svc.invite_user(email, full_name, _roles(roles))

        return standard_response(
            True,
            {
                "status": result.get("status"),
                "user": email,
            },
            _("User invited"),
        )
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_roles(ADMIN_ROLE_NAME)
def resend_invite(email: str):
    """Resend invite."""
    try:
        result = svc.resend_invite(email)

        return standard_response(
            True,
            {
                "status": result.get("status"),
                "user": email,
            },
            _("Invite resent"),
        )
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_roles(ADMIN_ROLE_NAME)
def update_user_roles(email: str, roles):
    """UC-07 / FR-1.7: Update user roles."""
    try:
        result = svc.update_user_roles(email, _roles(roles))

        return standard_response(
            True,
            result,
            _("User roles updated"),
        )
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_roles(ADMIN_ROLE_NAME)
def set_user_enabled(email: str, enabled):
    """UC-07: Enable/disable user."""
    try:
        result = svc.set_user_enabled(email, enabled)

        return standard_response(
            True,
            result,
            _("User state updated"),
        )
    except Exception as e:
        return handle_api_error(e)
