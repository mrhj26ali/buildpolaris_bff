import frappe


@frappe.whitelist(allow_guest=True)
def ping():
    """
    Health check endpoint for PWA/API smoke tests.
    """
    return {
        "status": "ok",
        "app": "buildpolaris_bff",
        "framework": "frappe",
        "version": getattr(frappe, "__version__", "unknown"),
    }
