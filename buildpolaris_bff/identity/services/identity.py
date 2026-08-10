import datetime
import hashlib

import frappe
from frappe import _
from buildpolaris_bff.shared.crypto_utils import generate_secure_token
from buildpolaris_bff.shared.security_log import log_security_event
from buildpolaris_bff.shared.erpnext_bridge import (
    add_company_permission,
    create_company,
    get_user_company,
    set_user_fields,
    set_platform_roles,
    sudo_as_administrator,
)
from buildpolaris_bff.install import ADMIN_ROLE_NAME, get_platform_role_names


def register_new_tenant(company_name: str, admin_email: str, admin_first_name: str, password: str = None):
    """UC-01: Creates isolated company and disabled admin user."""
    if frappe.db.exists("Company", company_name):
        frappe.throw(_("Company already exists"))

    raw_token, _ = generate_secure_token()

    abbr = hashlib.md5(company_name.encode("utf-8")).hexdigest()[:5].upper()
    expiry = frappe.utils.data.now_datetime() + datetime.timedelta(hours=24)

    with sudo_as_administrator():
        company = create_company(company_name, abbr, "United States", "USD")

        user = frappe.get_doc({
            "doctype": "User",
            "email": admin_email,
            "first_name": admin_first_name,
            "company": company,
            "bp_company": company,
            "enabled": 0,
            "user_type": "System User",
            "send_welcome_email": 0,
            "bp_activation_token": raw_token,
            "bp_activation_expiry": expiry,
        })
        user.append("roles", {"role": ADMIN_ROLE_NAME})

        if password:
            user.new_password = password

        user.insert(ignore_permissions=True)
        add_company_permission(admin_email, company)
        log_security_event("Tenant Created", {"company": company, "user": admin_email})

    return {"status": "success", "company": company, "token": raw_token}


def activate_account(token: str, password: str = None):
    """UC-01/UC-02: Activates user account. Requires password for invite activation."""
    if not token:
        frappe.throw(_("Invalid or expired token"))

    user_name = frappe.db.get_value("User", {"bp_activation_token": token}, "name")
    invite_mode = False

    if not user_name:
        user_name = frappe.db.get_value("User", {"bp_invite_token": token}, "name")
        invite_mode = bool(user_name)

    if not user_name:
        frappe.throw(_("Invalid or expired token"))

    with sudo_as_administrator():
        user = frappe.get_doc("User", user_name)

        if invite_mode and user.bp_needs_password and not password:
            return {"status": "password_required", "user": user_name}

        if password:
            user.new_password = password

        user.enabled = 1

        if invite_mode:
            user.bp_invite_status = "Accepted"
            user.bp_needs_password = 0
            user.bp_invite_token = None
            user.bp_invite_expiry = None
        else:
            user.bp_activation_token = None
            user.bp_activation_expiry = None

        user.save(ignore_permissions=True)
        log_security_event("Account Activated", {"user": user_name, "invite_mode": invite_mode})

    return {"status": "activated", "user": user_name}


def invite_user(email: str, full_name: str, roles: list[str], company: str = None):
    """UC-02/UC-05: Invites new user. Requires Admin role."""
    if ADMIN_ROLE_NAME not in frappe.get_roles():
        frappe.throw(_("Not authorized to invite users"), frappe.PermissionError)

    if frappe.db.exists("User", email):
        frappe.throw(_("User already exists"))

    raw_token, _ = generate_secure_token()
    expiry = frappe.utils.data.now_datetime() + datetime.timedelta(hours=24)
    company_value = company or get_user_company(frappe.session.user)
    if not company_value:
        frappe.throw(_("Unable to determine company for the invitation"))

    with sudo_as_administrator():
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": full_name,
            "bp_company": company_value,
            "enabled": 0,
            "user_type": "System User",
            "send_welcome_email": 0,
            "bp_invite_token": raw_token,
            "bp_invite_expiry": expiry,
            "bp_needs_password": 1,
            "bp_invite_status": "Pending",
            "bp_invited_by": frappe.session.user,
        })

        for role in roles:
            user.append("roles", {"role": role})

        user.insert(ignore_permissions=True)
        add_company_permission(email, company_value)
        log_security_event("User Invited", {"user": email, "roles": roles, "company": company_value})

    return {"status": "invited", "token": raw_token}


def get_session_context():
    """UC-03: Returns current user context with resolved persona."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"), frappe.AuthenticationError)

    user = frappe.get_doc("User", frappe.session.user)
    from buildpolaris_bff.identity.services.persona import resolve_persona
    persona = resolve_persona([r.role for r in user.roles])
    company = get_user_company(user.email) or user.company

    return {
        "user": user.name,
        "full_name": user.full_name,
        "email": user.email,
        "company": company,
        "persona": persona,
        "roles": [r.role for r in user.roles],
        "is_admin": ADMIN_ROLE_NAME in [r.role for r in user.roles],
    }


def update_user_roles(email: str, roles: list[str]):
    """UC-07: Updates tenant roles while protecting the last admin."""
    user = frappe.get_doc("User", email)
    user_company = get_user_company(email) or user.company
    current_roles = [r.role for r in user.roles]
    is_current_admin = ADMIN_ROLE_NAME in current_roles
    is_target_admin = ADMIN_ROLE_NAME in roles

    if is_current_admin and not is_target_admin:
        admins = frappe.db.sql("""
            SELECT COUNT(DISTINCT u.name)
            FROM `tabUser` u
            JOIN `tabHas Role` r ON u.name = r.parent
            WHERE u.company = %s AND u.enabled = 1 AND r.role = %s
        """, (user_company, ADMIN_ROLE_NAME))[0][0]

        if admins <= 1:
            frappe.throw(_("Cannot demote the last admin of the company"))

    set_platform_roles(email, roles)
    log_security_event("User Roles Updated", {"user": email, "roles": roles})
    return {"status": "roles_updated", "user": email}


def demote_admin(email: str):
    """UC-07: Prevents demoting the last admin in a company."""
    user = frappe.get_doc("User", email)
    company = user.company

    admins = frappe.db.sql("""
        SELECT COUNT(DISTINCT u.name) 
        FROM `tabUser` u
        JOIN `tabHas Role` r ON u.name = r.parent
        WHERE u.company = %s AND u.enabled = 1 AND r.role = %s
    """, (company, ADMIN_ROLE_NAME))[0][0]

    if admins <= 1:
        frappe.throw(_("Cannot demote the last admin of the company"))

    user.roles = [r for r in user.roles if r.role != ADMIN_ROLE_NAME]
    user.save(ignore_permissions=True)
