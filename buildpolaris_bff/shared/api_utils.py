import frappe
from frappe import _


def standard_response(
    success: bool = True,
    data=None,
    message: str | None = None,
    error_code: str | None = None,
    http_status_code: int = 200,
):
    """
    Standard BFF response envelope.
    The PWA client understands this envelope and unwraps `data`.
    """
    response = getattr(frappe.local, "response", None)

    if response is None:
        frappe.local.response = frappe._dict()
        response = frappe.local.response

    response["http_status_code"] = http_status_code

    return {
        "success": success,
        "data": data,
        "message": message or ("Success" if success else "An error occurred"),
        "error_code": error_code,
    }


def handle_api_error(e: Exception):
    """
    Convert known Frappe exceptions into standardized BFF error responses.
    """
    from buildpolaris_bff.shared.security_log import log_security_event

    if isinstance(e, frappe.PermissionError):
        log_security_event(
            "API_PERMISSION_ERROR",
            {
                "user": frappe.session.user,
                "error": str(e),
            },
        )
        return standard_response(
            False,
            None,
            str(e) or _("Not authorized"),
            error_code="PERMISSION_DENIED",
            http_status_code=403,
        )

    if isinstance(e, frappe.AuthenticationError):
        return standard_response(
            False,
            None,
            str(e) or _("Authentication required"),
            error_code="AUTH_REQUIRED",
            http_status_code=401,
        )

    if isinstance(e, frappe.ValidationError):
        return standard_response(
            False,
            None,
            str(e) or _("Validation failed"),
            error_code="VALIDATION_ERROR",
            http_status_code=400,
        )

    frappe.log_error(
        title="BuildPolaris API Error",
        message=frappe.get_traceback(),
    )

    return standard_response(
        False,
        None,
        _("Internal server error"),
        error_code="INTERNAL_ERROR",
        http_status_code=500,
    )
