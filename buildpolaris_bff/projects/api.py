"""
Projects module - HTTP adapters only (NFR-MAINT.1). Every function here
does Role/permission assertion (delegated to the services/ layer) + shape
validation, then calls exactly one services/ function - no business logic
lives here.

buildpolaris_pwa's CreateProjectDialog.tsx / projectsApi.ts already call
buildpolaris_bff.projects.api.create_project and
buildpolaris_bff.projects.api.get_project_summary by these exact dotted
paths - this module is what makes those calls resolve instead of 404ing.
"""
import frappe

from buildpolaris_bff.shared.api_envelope import success, api_guard
from buildpolaris_bff.projects.services import project_service, project_summary_service


@frappe.whitelist()
@api_guard
def create_project(project_name, description=None, expected_start_date=None, expected_end_date=None):
	return success(project_service.create_project(
		project_name=project_name, description=description,
		expected_start_date=expected_start_date, expected_end_date=expected_end_date,
	))


@frappe.whitelist()
@api_guard
def get_project(project):
	return success(project_service.get_project(project))


@frappe.whitelist()
@api_guard
def list_projects(status=None):
	return success(project_service.list_projects(status=status))


@frappe.whitelist()
@api_guard
def update_project(project, updates):
	if isinstance(updates, str):
		updates = frappe.parse_json(updates)
	return success(project_service.update_project(project, updates))


@frappe.whitelist()
@api_guard
def get_project_summary(project):
	return success(project_summary_service.get_project_summary(project))
