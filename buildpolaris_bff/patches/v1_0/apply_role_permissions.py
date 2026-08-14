"""Apply the platform role-permission matrix to every custom DocType.

Runs once per site during migration. Child tables inherit their parent's
permissions and are intentionally skipped. The matrix is also persisted back
into each DocType's JSON definition so the change survives future syncs.
"""

import json
import os

import frappe

ROLE_ADMIN = "BuildPolaris Admin"
ROLE_OWNER = "BuildPolaris Owner"
ROLE_PROJECT_MANAGER = "BuildPolaris Project Manager"
ROLE_ACCOUNTING = "BuildPolaris Accounting"
ROLE_DOCUMENT_CONTROLLER = "BuildPolaris Document Controller"
ROLE_SITE_SUPERINTENDENT = "BuildPolaris Site Superintendent"
ROLE_SAFETY_OFFICER = "BuildPolaris Safety Officer"
ROLE_SUBCONTRACTOR = "BuildPolaris Subcontractor"

FULL_ACCESS = {"read": 1, "write": 1, "create": 1, "delete": 1, "email": 1, "export": 1, "print": 1, "report": 1, "share": 1}
WRITE_ACCESS = {"read": 1, "write": 1, "create": 1, "email": 1, "export": 1, "print": 1, "report": 1, "share": 1}
READ_ACCESS = {"read": 1, "email": 1, "export": 1, "print": 1, "report": 1}

PERMISSION_MATRIX = {
	"Task Dependency": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_ACCOUNTING: READ_ACCESS, ROLE_DOCUMENT_CONTROLLER: READ_ACCESS, ROLE_SITE_SUPERINTENDENT: READ_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
	"Schedule Baseline": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_ACCOUNTING: READ_ACCESS, ROLE_DOCUMENT_CONTROLLER: READ_ACCESS, ROLE_SITE_SUPERINTENDENT: READ_ACCESS},
	"Cost Code": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_ACCOUNTING: WRITE_ACCESS, ROLE_DOCUMENT_CONTROLLER: READ_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
	"Commitment": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_ACCOUNTING: WRITE_ACCESS, ROLE_DOCUMENT_CONTROLLER: READ_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
	"Change Event": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_ACCOUNTING: WRITE_ACCESS, ROLE_DOCUMENT_CONTROLLER: READ_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
	"Pay Application": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_ACCOUNTING: WRITE_ACCESS, ROLE_DOCUMENT_CONTROLLER: READ_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
	"RFI": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_ACCOUNTING: READ_ACCESS, ROLE_DOCUMENT_CONTROLLER: WRITE_ACCESS, ROLE_SITE_SUPERINTENDENT: WRITE_ACCESS, ROLE_SUBCONTRACTOR: WRITE_ACCESS},
	"Submittal Package": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_DOCUMENT_CONTROLLER: WRITE_ACCESS, ROLE_SUBCONTRACTOR: WRITE_ACCESS},
	"Transmittal": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: READ_ACCESS, ROLE_DOCUMENT_CONTROLLER: WRITE_ACCESS},
	"Meeting Series": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS},
	"Meeting Minutes": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS},
	"Action Item": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_SITE_SUPERINTENDENT: WRITE_ACCESS},
	"Route Step": {ROLE_ADMIN: FULL_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_DOCUMENT_CONTROLLER: WRITE_ACCESS},
	"Escalation Log": {ROLE_ADMIN: FULL_ACCESS, ROLE_PROJECT_MANAGER: READ_ACCESS},
	"Drawing": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_DOCUMENT_CONTROLLER: WRITE_ACCESS, ROLE_SITE_SUPERINTENDENT: READ_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
	"Drawing Revision": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_DOCUMENT_CONTROLLER: WRITE_ACCESS, ROLE_SITE_SUPERINTENDENT: READ_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
	"Drawing Annotation": {ROLE_ADMIN: FULL_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_SITE_SUPERINTENDENT: WRITE_ACCESS},
	"Daily Log": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: READ_ACCESS, ROLE_SITE_SUPERINTENDENT: WRITE_ACCESS},
	"JSA": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_SITE_SUPERINTENDENT: WRITE_ACCESS, ROLE_SAFETY_OFFICER: WRITE_ACCESS},
	"Safety Incident": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_SITE_SUPERINTENDENT: WRITE_ACCESS, ROLE_SAFETY_OFFICER: WRITE_ACCESS},
	"Punch List Item": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_SITE_SUPERINTENDENT: WRITE_ACCESS, ROLE_SUBCONTRACTOR: WRITE_ACCESS},
	"Closing Record": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_ACCOUNTING: WRITE_ACCESS, ROLE_DOCUMENT_CONTROLLER: WRITE_ACCESS},
	"Substantial Completion Certificate": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: WRITE_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS},
	"Lien Waiver": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_ACCOUNTING: WRITE_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
	"Consent Of Surety": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_ACCOUNTING: WRITE_ACCESS},
	"Contractors Affidavit": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_ACCOUNTING: WRITE_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
	"OM Manual": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_DOCUMENT_CONTROLLER: WRITE_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
	"Warranty Document": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_DOCUMENT_CONTROLLER: WRITE_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
}


def execute():
	app_path = frappe.get_app_path("buildpolaris_bff")
	for doctype, role_permissions in PERMISSION_MATRIX.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		try:
			persist_to_doctype_json(app_path, doctype, role_permissions)
			apply_to_database(doctype, role_permissions)
		except Exception:
			frappe.log_error(
				title=f"BuildPolaris role matrix failed: {doctype}",
				message=frappe.get_traceback(),
			)


def build_permission_rows(role_permissions):
	rows = [{"role": "System Manager", **FULL_ACCESS}]
	for role, level in role_permissions.items():
		rows.append({"role": role, **level})
	return rows


def persist_to_doctype_json(app_path, doctype, role_permissions):
	module = frappe.db.get_value("DocType", doctype, "module")
	if not module:
		return
	json_path = os.path.join(
		app_path,
		frappe.scrub(module),
		"doctype",
		frappe.scrub(doctype),
		frappe.scrub(doctype) + ".json",
	)
	if not os.path.exists(json_path):
		return
	with open(json_path, "r") as handle:
		data = json.load(handle)
	if data.get("istable"):
		return
	data["permissions"] = build_permission_rows(role_permissions)
	with open(json_path, "w") as handle:
		json.dump(data, handle, indent=1)


def apply_to_database(doctype, role_permissions):
	doc = frappe.get_doc("DocType", doctype)
	if doc.istable:
		return
	doc.permissions = []
	for row in build_permission_rows(role_permissions):
		doc.append("permissions", row)
	doc.save(ignore_permissions=True)
