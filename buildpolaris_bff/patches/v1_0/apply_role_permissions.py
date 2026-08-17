"""Apply the platform role-permission matrix to every custom DocType.

Runs once per site during migration. Child tables inherit their parent's
permissions and are intentionally skipped. The matrix is also persisted back
into each DocType's JSON definition so the change survives future syncs.

Copilot Thread / Copilot Message are deliberately NOT in this matrix - their
if_owner-scoped permissions are defined directly in their own doctype JSON
(a generic role->access-level matrix has no if_owner concept), and this
patch only ever touches doctypes it's explicitly told about.

Account Activation Token is also deliberately NOT in this matrix - it holds
hashed single-use tokens (shared/crypto_utils.py, NFR-SEC.3) and is written
exclusively via ignore_permissions=True service calls
(registration_service.py / invitation_service.py); no BuildPolaris Role,
including Admin, should be able to browse or query it directly. Leaving it
out of the matrix means it keeps Frappe's own default (System Manager /
Administrator only), which is exactly the intended posture.
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
	"Project": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_ACCOUNTING: READ_ACCESS, ROLE_DOCUMENT_CONTROLLER: READ_ACCESS, ROLE_SITE_SUPERINTENDENT: READ_ACCESS, ROLE_SAFETY_OFFICER: READ_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
	# Native ERPNext doctype, same as Project - the WBS lives here per ERD
	# ("Task (under Project), extended with custom fields, never a shadow
	# schedule table"), so it needs the same explicit BuildPolaris-owned
	# permission set every other doctype gets; stock ERPNext ships its own
	# Task permissions (Projects User/Manager) which this replaces, same as
	# Project. Site Superintendent gets WRITE (not just READ, unlike
	# Task Dependency below) - field logging of day-to-day task progress
	# against the schedule is a normal part of that role, matching the
	# WRITE access it already has on Daily Log.
	"Task": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_ACCOUNTING: READ_ACCESS, ROLE_DOCUMENT_CONTROLLER: READ_ACCESS, ROLE_SITE_SUPERINTENDENT: WRITE_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
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
	"Agent Action Approval": {ROLE_ADMIN: FULL_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_ACCOUNTING: WRITE_ACCESS, ROLE_OWNER: WRITE_ACCESS, ROLE_DOCUMENT_CONTROLLER: READ_ACCESS},
	"Agent Mutation Log": {ROLE_ADMIN: FULL_ACCESS, ROLE_PROJECT_MANAGER: READ_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_ACCOUNTING: READ_ACCESS},
	"AI Document Index": {ROLE_ADMIN: FULL_ACCESS, ROLE_PROJECT_MANAGER: READ_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_ACCOUNTING: READ_ACCESS, ROLE_DOCUMENT_CONTROLLER: READ_ACCESS, ROLE_SUBCONTRACTOR: READ_ACCESS},
	# Closeout Document is a real top-level doctype (not a child table -
	# unlike Media Capture and RFI Watcher, which both have istable=1 and
	# are correctly excluded from this matrix per the module docstring
	# above). It's Closing Record's attached-files collection, so it
	# mirrors Closing Record's own access pattern exactly.
	# Populated only by evm_service.capture_nightly_snapshot() today (no
	# read endpoint exists yet) - permissioned now anyway so a future
	# trend-chart feature isn't blocked by a second missing-permission
	# gap, consistent with these roles' access to the live
	# get_evm_snapshot endpoint above.
	"EVM Snapshot": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: READ_ACCESS, ROLE_ACCOUNTING: READ_ACCESS},
	"Closeout Document": {ROLE_ADMIN: FULL_ACCESS, ROLE_OWNER: READ_ACCESS, ROLE_PROJECT_MANAGER: WRITE_ACCESS, ROLE_ACCOUNTING: WRITE_ACCESS, ROLE_DOCUMENT_CONTROLLER: WRITE_ACCESS},
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
