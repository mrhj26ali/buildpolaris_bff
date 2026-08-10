import datetime

import frappe
from frappe import _
from frappe.utils import now_datetime

from buildpolaris_bff.identity.services.persona import resolve_persona
from buildpolaris_bff.install import (
    ADMIN_ROLE_NAME,
    PLATFORM_ROLES,
    get_platform_role_names,
)
from buildpolaris_bff.shared.crypto_utils import hash_token
from buildpolaris_bff.shared.erpnext_bridge import (
    add_company_permission,
    create_company,
    get_user_company,
    set_platform_roles,
    sudo_as_administrator,
)
from buildpolaris_bff.shared.security_log import log_security_event
from buildpolaris_bff.shared.tokens import (
    is_expired,
    issue_single_use_token,
    verify_single_use_token,
)


def _company_abbr(company_name: str) -> str:
    """
    Generate a short ERPNext company abbreviation.
    ERPNext requires a unique company abbreviation.
    """
    import hashlib

    return hashlib.sha256(company_name.encode("utf-8")).hexdigest()[:5].upper()


def _require_admin_role():
    """
    Ensure the current user is a BuildPolaris Admin.
    Administrator is allowed as a platform operator.
    """
    if frappe.session.user == "Administrator":
        return

    if ADMIN_ROLE_NAME not in frappe.get_roles():
        log_security_event(
            "ADMIN_ACTION_DENIED",
            {
                "user": frappe.session.user,
            },
        )
        frappe.throw(_("Only BuildPolaris Admin can perform this action"), frappe.PermissionError)


def _get_current_company() -> str:
    """
    Resolve the company for the current session user.
    """
    company = get_user_company(frappe.session.user)

    if company:
        return company

    rows = frappe.get_all(
        "User",
        filters={"name": frappe.session.user},
        fields=["company", "bp_company"],
        limit=1,
        ignore_permissions=True,
    )

    if rows:
        company = rows[0].bp_company or rows[0].company

    if not company:
        frappe.throw(_("Unable to determine company for the current user"), frappe.ValidationError)

    return company


def _assert_same_company(email: str) -> str:
    """
    Ensure target user belongs to the same company as the current admin.
    """
    target_company = get_user_company(email)

    if not target_company:
        rows = frappe.get_all(
            "User",
            filters={"name": email},
            fields=["company", "bp_company"],
            limit=1,
            ignore_permissions=True,
        )

        if rows:
            target_company = rows[0].bp_company or rows[0].company

    if frappe.session.user == "Administrator":
        return target_company or "Administrator"

    current_company = _get_current_company()

    if not target_company or target_company != current_company:
        log_security_event(
            "CROSS_COMPANY_ACCESS_DENIED",
            {
                "user": frappe.session.user,
                "target_user": email,
                "current_company": current_company,
                "target_company": target_company,
            },
        )
        frappe.throw(_("User does not belong to your company"), frappe.PermissionError)

    return current_company


def _validate_platform_roles(roles: list[str]):
    """
    Ensure only platform-defined roles can be assigned.
    """
    if not roles:
        frappe.throw(_("At least one role is required"), frappe.ValidationError)

    platform_roles = set(get_platform_role_names())
    invalid_roles = [role for role in roles if role not in platform_roles]

    if invalid_roles:
        frappe.throw(
            _("Invalid roles: {0}").format(", ".join(invalid_roles)),
            frappe.ValidationError,
        )


def _count_active_admins(company: str) -> int:
    """
    Count active BuildPolaris Admin users in a company.
    """
    if not company:
        return 0

    result = frappe.db.sql(
        """
        SELECT COUNT(DISTINCT u.name)
        FROM `tabUser` u
        JOIN `tabHas Role` r ON u.name = r.parent
        WHERE u.bp_company = %s
          AND u.enabled = 1
          AND r.role = %s
        """,
        (company, ADMIN_ROLE_NAME),
    )

    return int(result[0][0]) if result else 0


def available_roles():
    """
    FR-1.8 — role catalog for the checkbox UI.
    """
    return [
        {
            "role": role["role"],
            "description": role["description"],
            "persona": role["persona"],
        }
        for role in PLATFORM_ROLES
    ]


def list_tenant_users():
    """
    FR-1.7 — tenant user list.
    Returns users belonging to the current admin's company.
    """
    _require_admin_role()
    company = _get_current_company()
    platform_roles = set(get_platform_role_names())

    users = frappe.get_all(
        "User",
        filters={"bp_company": company},
        fields=["name", "email", "full_name", "enabled", "bp_invite_status"],
        order_by="full_name asc",
    )

    result = []

    for user in users:
        user_roles = frappe.get_roles(user.name)
        assigned_platform_roles = [role for role in user_roles if role in platform_roles]

        result.append(
            {
                "name": user.name,
                "email": user.email,
                "full_name": user.full_name,
                "enabled": int(user.enabled or 0),
                "bp_invite_status": user.bp_invite_status,
                "roles": assigned_platform_roles,
            }
        )

    return result


def register_new_tenant(
    company_name: str,
    admin_email: str,
    admin_first_name: str,
    password: str | None = None,
    country: str = "United States",
    currency: str = "USD",
):
    """
    UC-01 / FR-1.1 / FR-1.9:
    Create an isolated ERPNext Company and a disabled tenant Admin user.

    The activation token is stored hashed.
    The raw token is returned only for trusted internal/test usage.
    The public API layer must not return it.
    """
    if not company_name:
        frappe.throw(_("Company name is required"), frappe.ValidationError)

    if not admin_email:
        frappe.throw(_("Admin email is required"), frappe.ValidationError)

    if not admin_first_name:
        frappe.throw(_("Admin name is required"), frappe.ValidationError)

    admin_email = admin_email.strip().lower()

    if frappe.db.exists("Company", company_name):
        frappe.throw(_("Company already exists"), frappe.DuplicateEntryError)

    if frappe.db.exists("User", admin_email):
        frappe.throw(_("User already exists"), frappe.DuplicateEntryError)

    raw_token, hashed_token, expiry = issue_single_use_token()
    abbr = _company_abbr(company_name)

    with sudo_as_administrator():
        company = create_company(company_name, abbr, country, currency)

        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": admin_email,
                "first_name": admin_first_name,
                "company": company,
                "bp_company": company,
                "enabled": 0,
                "user_type": "System User",
                "send_welcome_email": 0,
                "bp_activation_token": hashed_token,
                "bp_activation_expiry": expiry,
            }
        )

        user.append("roles", {"role": ADMIN_ROLE_NAME})

        if password:
            user.new_password = password

        user.insert(ignore_permissions=True)

        add_company_permission(admin_email, company)

    log_security_event(
        "Tenant Created",
        {
            "company": company,
            "user": admin_email,
        },
    )

    return {
        "status": "success",
        "company": company,
        "activation_token": raw_token,
    }


def activate_account(token: str, password: str | None = None):
    """
    UC-01 / UC-02 / FR-1.2 / FR-1.4:
    Activate a tenant admin or invited user using a single-use token.
    Token storage is hashed.
    """
    if not token:
        return {"status": "invalid"}

    token_hash = hash_token(token)

    with sudo_as_administrator():
        user_name = frappe.db.get_value(
            "User",
            {"bp_activation_token": token_hash},
            "name",
        )

        invite_mode = False

        if not user_name:
            user_name = frappe.db.get_value(
                "User",
                {"bp_invite_token": token_hash},
                "name",
            )
            invite_mode = bool(user_name)

        if not user_name:
            log_security_event(
                "INVALID_ACTIVATION_TOKEN",
                {
                    "token_prefix": token[:8],
                },
            )
            return {"status": "invalid"}

        user = frappe.get_doc("User", user_name)

        stored_hash = user.bp_invite_token if invite_mode else user.bp_activation_token
        expiry = user.bp_invite_expiry if invite_mode else user.bp_activation_expiry

        if is_expired(expiry):
            log_security_event(
                "EXPIRED_ACTIVATION_TOKEN",
                {
                    "user": user.name,
                    "invite_mode": invite_mode,
                },
            )
            return {"status": "expired"}

        if not verify_single_use_token(token, stored_hash, expiry):
            log_security_event(
                "INVALID_ACTIVATION_TOKEN",
                {
                    "user": user.name,
                    "invite_mode": invite_mode,
                },
            )
            return {"status": "invalid"}

        if invite_mode and user.bp_needs_password and not password:
            return {
                "status": "password_required",
                "user": user.name,
            }

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

    log_security_event(
        "Account Activated",
        {
            "user": user_name,
            "invite_mode": invite_mode,
        },
    )

    return {
        "status": "activated",
        "user": user_name,
    }


def resend_activation(email: str):
    """
    Resend activation token.
    This endpoint intentionally returns a generic response to avoid user enumeration.
    """
    if not email:
        return {"status": "resent"}

    email = email.strip().lower()

    with sudo_as_administrator():
        user_name = frappe.db.get_value("User", email, "name")

        if user_name:
            user = frappe.get_doc("User", user_name)

            if not user.enabled:
                raw_token, hashed_token, expiry = issue_single_use_token()

                user.bp_activation_token = hashed_token
                user.bp_activation_expiry = expiry
                user.save(ignore_permissions=True)

                log_security_event(
                    "Activation Token Resent",
                    {
                        "user": user.name,
                    },
                )

    return {"status": "resent"}


def invite_user(email: str, full_name: str, roles: list[str], company: str | None = None):
    """
    UC-02 / FR-1.3:
    Invite a new user into the current admin's company.
    """
    _require_admin_role()

    if not email:
        frappe.throw(_("Email is required"), frappe.ValidationError)

    if not full_name:
        frappe.throw(_("Full name is required"), frappe.ValidationError)

    _validate_platform_roles(roles)

    email = email.strip().lower()

    if frappe.db.exists("User", email):
        frappe.throw(_("User already exists"), frappe.DuplicateEntryError)

    company_value = company or _get_current_company()
    raw_token, hashed_token, expiry = issue_single_use_token()

    with sudo_as_administrator():
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": full_name,
                "company": company_value,
                "bp_company": company_value,
                "enabled": 0,
                "user_type": "System User",
                "send_welcome_email": 0,
                "bp_invite_token": hashed_token,
                "bp_invite_expiry": expiry,
                "bp_needs_password": 1,
                "bp_invite_status": "Pending",
                "bp_invited_by": frappe.session.user,
            }
        )

        for role in roles:
            user.append("roles", {"role": role})

        user.insert(ignore_permissions=True)

        add_company_permission(email, company_value)

    log_security_event(
        "User Invited",
        {
            "user": email,
            "roles": roles,
            "company": company_value,
        },
    )

    return {
        "status": "invited",
        "invite_token": raw_token,
    }


def resend_invite(email: str):
    """
    Resend invite token for a pending invite.
    The old invite token is invalidated by replacing it with a new hashed token.
    """
    _require_admin_role()
    _assert_same_company(email)

    email = email.strip().lower()

    with sudo_as_administrator():
        user_name = frappe.db.get_value("User", email, "name")

        if not user_name:
            frappe.throw(_("User not found"), frappe.ValidationError)

        user = frappe.get_doc("User", user_name)

        if user.enabled:
            frappe.throw(_("User is already active"), frappe.ValidationError)

        raw_token, hashed_token, expiry = issue_single_use_token()

        user.bp_invite_token = hashed_token
        user.bp_invite_expiry = expiry
        user.bp_needs_password = 1
        user.bp_invite_status = "Pending"
        user.bp_invited_by = frappe.session.user
        user.save(ignore_permissions=True)

    log_security_event(
        "Invite Token Resent",
        {
            "user": email,
        },
    )

    return {
        "status": "resent",
        "invite_token": raw_token,
    }


def get_session_context():
    """
    UC-03 / FR-1.8:
    Return current user context with resolved persona.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"), frappe.AuthenticationError)

    current_user = frappe.session.user

    with sudo_as_administrator():
        user = frappe.get_doc("User", current_user)

    roles = [role.role for role in user.roles]
    persona = resolve_persona(roles)
    company = get_user_company(current_user) or getattr(user, "bp_company", None) or getattr(user, "company", None)

    return {
        "user": user.name,
        "full_name": user.full_name,
        "email": user.email,
        "company": company,
        "persona": persona,
        "roles": roles,
        "is_admin": ADMIN_ROLE_NAME in roles,
    }


def update_user_roles(email: str, roles: list[str]):
    """
    UC-07 / FR-1.7 / FR-1.10:
    Update tenant roles while protecting the last admin.
    """
    _require_admin_role()
    target_company = _assert_same_company(email)
    _validate_platform_roles(roles)

    email = email.strip().lower()

    with sudo_as_administrator():
        user = frappe.get_doc("User", email)

    current_roles = [role.role for role in user.roles]
    is_current_admin = ADMIN_ROLE_NAME in current_roles
    is_target_admin = ADMIN_ROLE_NAME in roles

    if is_current_admin and not is_target_admin:
        admins = _count_active_admins(target_company)

        if admins <= 1:
            frappe.throw(_("Cannot demote the last admin of the company"), frappe.ValidationError)

    set_platform_roles(email, roles)

    log_security_event(
        "User Roles Updated",
        {
            "user": email,
            "roles": roles,
        },
    )

    return {
        "status": "roles_updated",
        "user": email,
    }


def set_user_enabled(email: str, enabled):
    """
    UC-07:
    Enable/disable a user inside the same company.
    """
    _require_admin_role()
    target_company = _assert_same_company(email)

    email = email.strip().lower()
    enabled_bool = enabled in (True, "true", "1", 1)

    if not enabled_bool and email == frappe.session.user:
        frappe.throw(_("You cannot disable your own account"), frappe.ValidationError)

    user_roles = frappe.get_roles(email)

    if not enabled_bool and ADMIN_ROLE_NAME in user_roles:
        admins = _count_active_admins(target_company)

        if admins <= 1:
            frappe.throw(_("Cannot disable the last admin of the company"), frappe.ValidationError)

    with sudo_as_administrator():
        user = frappe.get_doc("User", email)
        user.enabled = 1 if enabled_bool else 0
        user.save(ignore_permissions=True)

    log_security_event(
        "User Enabled State Updated",
        {
            "user": email,
            "enabled": enabled_bool,
        },
    )

    return {
        "status": "user_updated",
        "user": email,
        "enabled": enabled_bool,
    }


def demote_admin(email: str):
    """
    UC-07:
    Remove admin role from a user while protecting the last admin.
    """
    _require_admin_role()
    target_company = _assert_same_company(email)

    email = email.strip().lower()

    with sudo_as_administrator():
        user = frappe.get_doc("User", email)

    current_roles = [role.role for role in user.roles]

    if ADMIN_ROLE_NAME not in current_roles:
        return {
            "status": "no_change",
            "user": email,
        }

    admins = _count_active_admins(target_company)

    if admins <= 1:
        frappe.throw(_("Cannot demote the last admin of the company"), frappe.ValidationError)

    next_roles = [role for role in current_roles if role != ADMIN_ROLE_NAME]
    set_platform_roles(email, next_roles)

    log_security_event(
        "Admin Demoted",
        {
            "user": email,
        },
    )

    return {
        "status": "admin_demoted",
        "user": email,
    }
