"""
FR-2.2: typed dependencies with lag, held in Task Dependency (native
Task.depends_on can't type or lag). Every save mirrors a simplified entry
back into Task.depends_on so ERPNext's own Task/Gantt views stay consistent
for anyone who opens the Desk UI directly.
"""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role

VALID_TYPES = {"FS", "SS", "FF", "SF"}


def create_dependency(project, predecessor, successor, type="FS", lag_days=0, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	if type not in VALID_TYPES:
		raise ValidationError(f"type must be one of {VALID_TYPES}.")
	if predecessor == successor:
		raise ValidationError("A task cannot depend on itself.")
	if frappe.db.exists("Task Dependency", {"predecessor": predecessor, "successor": successor}):
		raise ValidationError("This dependency already exists.")

	_assert_no_cycle(project, predecessor, successor)

	doc = frappe.get_doc({
		"doctype": "Task Dependency",
		"project": project,
		"predecessor": predecessor,
		"successor": successor,
		"type": type,
		"lag_days": lag_days,
	})
	doc.insert()

	_mirror_to_native_task(successor, predecessor)
	return doc.as_dict()


def delete_dependency(dependency: str, deleted_by: str | None = None):
	deleted_by = deleted_by or frappe.session.user
	doc = frappe.get_doc("Task Dependency", dependency)
	assert_project_permission(doc.project, ptype="write", user=deleted_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=deleted_by)

	predecessor, successor = doc.predecessor, doc.successor
	frappe.delete_doc("Task Dependency", dependency, ignore_permissions=True)
	_unmirror_from_native_task(successor, predecessor)
	return {"deleted": dependency}


def _mirror_to_native_task(successor: str, predecessor: str):
	task_doc = frappe.get_doc("Task", successor)
	existing = {row.task for row in (task_doc.get("depends_on") or [])}
	if predecessor not in existing:
		task_doc.append("depends_on", {"task": predecessor})
		task_doc.flags.ignore_links = True
		task_doc.save(ignore_permissions=True)


def _unmirror_from_native_task(successor: str, predecessor: str):
	task_doc = frappe.get_doc("Task", successor)
	rows = task_doc.get("depends_on") or []
	task_doc.set("depends_on", [r for r in rows if r.task != predecessor])
	task_doc.save(ignore_permissions=True)


def _assert_no_cycle(project: str, predecessor: str, successor: str):
	"""BFS from `successor` forward through existing dependencies - if we
	reach `predecessor`, adding predecessor->successor would close a cycle."""
	edges = frappe.get_all("Task Dependency", filters={"project": project},
	                        fields=["predecessor", "successor"])
	adjacency = {}
	for e in edges:
		adjacency.setdefault(e.predecessor, []).append(e.successor)

	stack = [successor]
	seen = set()
	while stack:
		current = stack.pop()
		if current == predecessor:
			raise ValidationError("This dependency would create a cyclic schedule (not computable).")
		if current in seen:
			continue
		seen.add(current)
		stack.extend(adjacency.get(current, []))
