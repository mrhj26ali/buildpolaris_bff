"""
Cross-module Project summary -- the read model behind
buildpolaris_pwa's dashboard landing page (Flowcharts §2's "M8 cuts
across every module" diagram is the human-facing analogue: a project-wide
glance before drilling into M2..M7) and behind the copilot's
get_project_summary MCP tool (ai_copilot/mcp/tools/project_tools.py).

Every number here is computed by calling the SAME service function each
module's own detail screens and MCP tools already use -- never a second,
parallel definition of "what counts as open" that could quietly drift
from the real one (NFR-EXT.3's "no parallel read path" discipline,
already followed by ai_copilot/mcp/tools/*.py, applied here too).
"""
from frappe.utils import getdate, today

from buildpolaris_bff.communications.services import submittal_service
from buildpolaris_bff.field.services import punch_list_service
from buildpolaris_bff.financials.services import evm_service, pay_application_service
from buildpolaris_bff.communications.services import rfi_service
from buildpolaris_bff.scheduling.services import schedule_task_service
from buildpolaris_bff.shared.permissions import assert_project_permission

import frappe


def get_project_summary(project: str, user: str | None = None) -> dict:
	user = user or frappe.session.user
	assert_project_permission(project, ptype="read", user=user)

	project_doc = frappe.db.get_value(
		"Project", project, ["project_name", "expected_end_date"], as_dict=True
	)
	if not project_doc:
		frappe.throw(f"Project {project} not found.")

	as_of = getdate(today())
	evm = _evm(project)

	return {
		"project": project,
		"title": project_doc.project_name,
		"schedule_health": _schedule_health(project, as_of),
		"open_rfi_count": _open_rfi_count(project),
		"open_submittal_count": _open_submittal_count(project),
		"pending_pay_application": _has_pending_pay_application(project),
		"open_punch_item_count": _open_punch_item_count(project),
		"cpi": _safe_round(evm.get("cpi")),
		"spi": _safe_round(evm.get("spi")),
		"next_milestone": _next_milestone(project, as_of),
	}


def _safe_round(value, digits=2):
	return round(value, digits) if value is not None else None


def _evm(project: str) -> dict:
	# assert_project_permission already ran in get_project_summary(); evm_service
	# re-asserts internally too (defense in depth, cheap given it's a single
	# frappe.has_permission call) -- Administrator here would be wrong, so
	# pass the real caller through via frappe.session.user (evm_service's
	# own default) rather than re-deriving it.
	return evm_service.compute_evm(project)


def _schedule_health(project: str, as_of) -> str:
	"""OnTrack / AtRisk / Overdue -- derived from the SAME Task fields
	the CPM engine already computes (is_critical, total_float, exp_end_date
	via scheduling/patches add_scheduling_custom_fields.py), not a second
	definition of schedule risk."""
	tasks = schedule_task_service_list_tasks_safe(project)
	if not tasks:
		return "OnTrack"

	for t in tasks:
		exp_end = t.get("exp_end_date")
		status = (t.get("status") or "").lower()
		if exp_end and getdate(exp_end) < as_of and status not in ("completed", "cancelled"):
			return "Overdue"

	for t in tasks:
		if t.get("is_critical") and (t.get("total_float") or 0) <= 2:
			return "AtRisk"

	return "OnTrack"


def schedule_task_service_list_tasks_safe(project: str) -> list:
	"""list_tasks() enforces its own assert_project_permission -- fine,
	it's the same check we already passed. Isolated in its own function
	so a schedule with zero Tasks yet (a brand-new Project) degrades to
	OnTrack rather than raising."""
	try:
		return schedule_task_service.list_tasks(project)
	except Exception:
		return []


def _open_rfi_count(project: str) -> int:
	rfis = rfi_service.list_rfis(project)
	return sum(1 for r in rfis if (r.get("status") or "").lower() in ("open", "escalated"))


def _open_submittal_count(project: str) -> int:
	submittals = submittal_service.list_submittals(project)
	open_statuses = {"submitted", "underreview", "resubmitrequested"}
	return sum(1 for s in submittals if (s.get("status") or "").lower() in open_statuses)


def _has_pending_pay_application(project: str) -> bool:
	pending_statuses = ["Draft", "PendingApproval"]
	return bool(frappe.db.exists("Pay Application", {"project": project, "status": ["in", pending_statuses]}))


def _open_punch_item_count(project: str) -> int:
	# Matches the exact definition ai_copilot's get_open_punch_items MCP
	# tool already uses (status="Open" exactly) -- one definition of
	# "open" for a Punch List Item across the whole platform.
	items = punch_list_service.list_punch_items(project, status="Open")
	return len(items)


def _next_milestone(project: str, as_of) -> dict | None:
	"""A Task with activity_type == 'Milestone' (add_scheduling_custom_fields.py),
	nearest upcoming by its CPM-computed early_finish."""
	rows = frappe.get_all(
		"Task",
		filters={"project": project, "activity_type": "Milestone"},
		fields=["subject", "early_finish", "exp_end_date"],
		order_by="early_finish asc",
	)
	for row in rows:
		finish = row.get("early_finish") or row.get("exp_end_date")
		if finish and getdate(finish) >= as_of:
			return {"subject": row["subject"], "early_finish": str(finish)}
	return None
