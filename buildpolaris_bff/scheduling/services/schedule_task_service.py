"""FR-2.1: WBS as native ERPNext Task records under a Project."""
import frappe

from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def create_task(project, subject, exp_start_date=None, exp_end_date=None, duration=None,
                 is_group=0, parent_task=None, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	doc = frappe.get_doc({
		"doctype": "Task",
		"project": project,
		"subject": subject,
		"exp_start_date": exp_start_date,
		"exp_end_date": exp_end_date,
		"duration": duration,
		"is_group": is_group,
		"parent_task": parent_task,
	})
	doc.insert()
	return doc.as_dict()


def update_task(task: str, updates: dict, updated_by: str | None = None):
	updated_by = updated_by or frappe.session.user
	doc = frappe.get_doc("Task", task)
	assert_project_permission(doc.project, ptype="write", user=updated_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=updated_by)

	allowed_fields = {"subject", "exp_start_date", "exp_end_date", "duration", "progress",
	                   "wbs_code", "activity_type", "constraint_type", "constraint_date"}
	for k, v in updates.items():
		if k in allowed_fields:
			doc.set(k, v)
	doc.save()
	return doc.as_dict()


def list_tasks(project: str, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	return frappe.get_all(
		"Task",
		filters={"project": project},
		fields=["name", "subject", "exp_start_date", "exp_end_date", "duration", "progress",
		        "is_group", "parent_task", "early_start", "early_finish", "late_start",
		        "late_finish", "total_float", "is_critical", "wbs_code", "activity_type"],
		order_by="exp_start_date asc",
	)
