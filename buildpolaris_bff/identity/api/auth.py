import frappe
import frappe.sessions
from frappe import _

from buildpolaris_bff.identity.services import identity as svc
from buildpolaris_bff.shared.api_utils import handle_api_error, standard_response
from buildpolaris_bff.shared.guards import require_authenticated_user
from buildpolaris_bff.shared.rate_limit import is_rate_limited


@frappe.whitelist(allow_guest=True)
def get_csrf_token():
    """
    Return Frappe CSRF token.
    The PWA uses cookie session authentication and must send the CSRF token
    on mutating requests.
    """
    token = frappe.sessions.get_csrf_token()
    frappe.db.commit()
    return token


@frappe.whitelist(allow_guest=True)
def register_tenant(
    company_name: str | None = None,
    admin_email: str | None = None,
    admin_name: str | None = None,
    admin_first_name: str | None = None,
    admin_password: str | None = None,
    password: str | None = None,
    country: str = "United States",
    currency: str = "USD",
):
    """
    UC-01 / FR-1.1:
    Register a new tenant.
    Rate limited.
    Does not return activation token over HTTP.
    """
    if is_rate_limited("register_tenant", limit=5, seconds=300):
        return standard_response(
            False,
            None,
            _("Too many registration attempts. Try again later."),
            error_code="RATE_LIMIT",
            http_status_code=429,
        )

    try:
        first_name = admin_first_name or admin_name
        final_password = admin_password or password

        result = svc.register_new_tenant(
            company_name=company_name,
            admin_email=admin_email,
            admin_first_name=first_name,
            password=final_password,
            country=country,
            currency=currency,
        )

        return standard_response(
            True,
            {
                "status": "success",
                "company": result.get("company"),
            },
            _("Tenant registered successfully"),
        )
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist(allow_guest=True)
def activate_account(token: str | None = None, password: str | None = None):
    """
    UC-01 / UC-02 / FR-1.2 / FR-1.4:
    Activate an account using a single-use token.
    Rate limited.
    """
    if is_rate_limited("activate_account", limit=10, seconds=300):
        return standard_response(
            False,
            None,
            _("Too many activation attempts. Try again later."),
            error_code="RATE_LIMIT",
            http_status_code=429,
        )

    try:
        result = svc.activate_account(token, password)

        return standard_response(
            True,
            result,
            _("Activation request processed"),
        )
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist(allow_guest=True)
def resend_activation(email: str | None = None):
    """
    Resend activation.
    Rate limited.
    Returns generic response to avoid user enumeration.
    """
    if is_rate_limited("resend_activation", limit=5, seconds=300):
        return standard_response(
            False,
            None,
            _("Too many attempts. Try again later."),
            error_code="RATE_LIMIT",
            http_status_code=429,
        )

    try:
        result = svc.resend_activation(email)

        return standard_response(
            True,
            result,
            _("If the account exists and is pending activation, an activation link has been sent."),
        )
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_authenticated_user
def get_session_context():
    """
    UC-03 / FR-1.8:
    Return session context for PWA bootstrap.
    """
    try:
        result = svc.get_session_context()

        return standard_response(
            True,
            result,
            _("Session context retrieved"),
        )
    except Exception as e:
        return handle_api_error(e)
