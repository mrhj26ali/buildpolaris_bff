"""FR-2.4: snapshot the current schedule as a named Baseline."""
import frappe
from frappe.utils import now_datetime

from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def create_baseline(project: str, label: str, created_by: str | None = None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	tasks = frappe.get_all(
		"Task", filters={"project": project, "is_group": 0},
		fields=["name", "exp_start_date", "exp_end_date", "duration"],
	)

	doc = frappe.get_doc({
		"doctype": "Schedule Baseline",
		"naming_series": "BASE-.YYYY.-.#####",
		"project": project,
		"label": label,
		"captured_at": now_datetime(),
	})
	for t in tasks:
		doc.append("snapshots", {
			"task": t.name,
			"planned_start": t.exp_start_date,
			"planned_finish": t.exp_end_date,
			"planned_duration": t.duration,
		})
	doc.insert()
	return doc.as_dict()


def get_baseline_variance(baseline: str, user: str | None = None):
	"""Supports the ERD's stated purpose ('variance tracking over time') -
	compares each snapshot's planned dates to the task's CURRENT dates."""
	doc = frappe.get_doc("Schedule Baseline", baseline)
	assert_project_permission(doc.project, ptype="read", user=user)

	variance = []
	for snap in doc.snapshots:
		current = frappe.db.get_value("Task", snap.task, ["exp_start_date", "exp_end_date"], as_dict=True)
		if not current:
			continue
		variance.append({
			"task": snap.task,
			"planned_start": snap.planned_start,
			"current_start": current.exp_start_date,
			"start_variance_days": (current.exp_start_date - snap.planned_start).days
				if (current.exp_start_date and snap.planned_start) else None,
			"planned_finish": snap.planned_finish,
			"current_finish": current.exp_end_date,
			"finish_variance_days": (current.exp_end_date - snap.planned_finish).days
				if (current.exp_end_date and snap.planned_finish) else None,
		})
	return variance


def list_baselines(project: str, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	return frappe.get_all("Schedule Baseline", filters={"project": project},
	                       fields=["name", "label", "captured_at"], order_by="captured_at desc")
