"""
Orchestrates CPM recomputation and persists results to native Task fields
(FR-2.3). Also the schedule-percent-complete read used by
financials/services/evm_service.py (FR-3.7's Scheduling half).
"""
import frappe
from frappe.utils import flt

from buildpolaris_bff.shared.permissions import assert_project_permission
from buildpolaris_bff.scheduling.services.cpm.critical_path import compute_cpm


def recompute_schedule(project: str, triggered_by: str | None = None) -> dict:
	"""FR-2.3: server-side CPM is the authoritative result. Persists
	early/late start/finish, total_float, is_critical onto Task, and fires
	FR-2.7 notifications when slippage or a critical-path change is
	detected relative to the PRIOR persisted state."""
	triggered_by = triggered_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=triggered_by)

	previous = {
		row.name: {"total_float": row.total_float, "is_critical": row.is_critical}
		for row in frappe.get_all(
			"Task", filters={"project": project, "is_group": 0},
			fields=["name", "total_float", "is_critical"],
		)
	}

	results = compute_cpm(project)

	changed_tasks = []
	for task_name, r in results.items():
		before = previous.get(task_name, {})
		became_critical = (not before.get("is_critical")) and r["is_critical"]
		slipped = before.get("total_float") is not None and r["total_float"] < flt(before.get("total_float"))
		if became_critical or slipped:
			changed_tasks.append({
				"task": task_name, "became_critical": became_critical, "slipped": slipped,
				"total_float": r["total_float"],
			})

		frappe.db.set_value("Task", task_name, {
			"early_start": r["early_start"],
			"early_finish": r["early_finish"],
			"late_start": r["late_start"],
			"late_finish": r["late_finish"],
			"total_float": r["total_float"],
			"is_critical": 1 if r["is_critical"] else 0,
		}, update_modified=False)

	frappe.db.commit()

	if changed_tasks:
		from buildpolaris_bff.scheduling.services.schedule_validation import notify_schedule_change
		notify_schedule_change(project, changed_tasks)

	return results


def get_project_percent_complete(project: str, as_of_date=None, user: str | None = None) -> float:
	"""Duration-weighted average of Task.progress - the schedule-derived
	half of FR-3.7's EVM calculation."""
	if user:
		assert_project_permission(project, ptype="read", user=user)

	tasks = frappe.get_all(
		"Task", filters={"project": project, "is_group": 0},
		fields=["duration", "progress"],
	)
	total_duration = sum(flt(t.duration) or 1 for t in tasks)
	if not total_duration:
		return 0.0
	weighted = sum((flt(t.duration) or 1) * flt(t.progress) for t in tasks)
	return round(weighted / total_duration, 2)
