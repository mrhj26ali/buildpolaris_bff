"""Liveness probe -- deliberately outside @api_guard/success() since it
must answer even if something deeper in the app is unhealthy, and
buildpolaris_pwa's bffClient.ping() (used for the PWA's own online/
offline detection, ARCH §5.5) expects a flat {status, app, framework}
shape, not the standard envelope."""
import frappe


@frappe.whitelist(allow_guest=True)
def ping():
	return {"status": "ok", "app": "buildpolaris_bff", "framework": "frappe"}
