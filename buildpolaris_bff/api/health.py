import frappe
from buildpolaris_bff.api.utils import standard_response

@frappe.whitelist()
def ping():
    """
    Health check endpoint to verify BFF operational status and API envelope contract.
    """
    return standard_response(
        success=True,
        data={"status": "ok", "app": "buildpolaris_bff", "framework": "Frappe v16"},
        message="BuildPolaris BFF is operational"
    )
