"""Scheduling - HTTP adapters only (NFR-MAINT.1)."""
import frappe

from buildpolaris_bff.shared.api_envelope import success
from buildpolaris_bff.scheduling.services import (
	baseline_service,
	lookahead_service,
	schedule_service,
	schedule_task_service,
	schedule_validation,
	task_dependency_service,
	what_if_service,
)


@frappe.whitelist()
def create_task(project, subject, exp_start_date=None, exp_end_date=None, duration=None,
                 is_group=0, parent_task=None):
	return success(schedule_task_service.create_task(
		project, subject, exp_start_date, exp_end_date, duration, is_group, parent_task
	))


@frappe.whitelist()
def update_task(task, updates):
	if isinstance(updates, str):
		updates = frappe.parse_json(updates)
	return success(schedule_task_service.update_task(task, updates))


@frappe.whitelist()
def list_tasks(project):
	return success(schedule_task_service.list_tasks(project))


@frappe.whitelist()
def create_dependency(project, predecessor, successor, type="FS", lag_days=0):
	return success(task_dependency_service.create_dependency(project, predecessor, successor, type, int(lag_days)))


@frappe.whitelist()
def delete_dependency(dependency):
	return success(task_dependency_service.delete_dependency(dependency))


@frappe.whitelist()
def recompute_schedule(project):
	return success(schedule_service.recompute_schedule(project))


@frappe.whitelist()
def preview_schedule_change(project, task_edits):
	if isinstance(task_edits, str):
		task_edits = frappe.parse_json(task_edits)
	return success(what_if_service.preview_schedule_change(project, task_edits))


@frappe.whitelist()
def run_health_check(project):
	return success(schedule_validation.run_health_check(project))


@frappe.whitelist()
def create_baseline(project, label):
	return success(baseline_service.create_baseline(project, label))


@frappe.whitelist()
def list_baselines(project):
	return success(baseline_service.list_baselines(project))


@frappe.whitelist()
def get_baseline_variance(baseline):
	return success(baseline_service.get_baseline_variance(baseline))


@frappe.whitelist()
def get_lookahead(project, weeks=3, as_of_date=None):
	return success(lookahead_service.get_lookahead(project, int(weeks), as_of_date))
