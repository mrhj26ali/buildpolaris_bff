"""
Central Role/Project permission assertion (NFR-SEC.1, NFR-SEC.4).

Every @frappe.whitelist() function in every module's api.py must call one
of these BEFORE any mutation - "reachable via HTTP" is never "authorized."
Tenant/Project isolation is enforced through native Frappe `User Permission`
records (FR-1.3), never an application-level filter a developer could omit -
these helpers assert against that layer, they don't reimplement it.
"""
import frappe

from buildpolaris_bff.shared.exceptions import PermissionDeniedError
from buildpolaris_bff.shared.security_log import log_security_event

PLATFORM_ROLES = [
	"BuildPolaris Admin",
	"BuildPolaris Owner",
	"BuildPolaris Project Manager",
	"BuildPolaris Accounting",
	"BuildPolaris Document Controller",
	"BuildPolaris Site Superintendent",
	"BuildPolaris Safety Officer",
	"BuildPolaris Subcontractor",
]


def get_user_roles(user: str | None = None) -> list[str]:
	user = user or frappe.session.user
	return frappe.get_roles(user)


def has_any_role(*roles: str, user: str | None = None) -> bool:
	user_roles = set(get_user_roles(user))
	return bool(user_roles.intersection(roles))


def assert_role(*roles: str, user: str | None = None):
	"""Raise PermissionDeniedError unless the caller holds at least one of
	the given Roles. System Manager always passes (bench/admin operations)."""
	user = user or frappe.session.user
	user_roles = set(get_user_roles(user))

	if "System Manager" in user_roles:
		return

	if not user_roles.intersection(roles):
		log_security_event(
			"UNAUTHORIZED_ROLE_ACCESS",
			{"user": user, "required_any_of": list(roles), "held_roles": list(user_roles)},
		)
		raise PermissionDeniedError(
			f"Requires one of: {', '.join(roles)}", error_code="ROLE_REQUIRED"
		)


def assert_project_permission(project: str, ptype: str = "read", user: str | None = None):
	"""Assert the caller's native `User Permission` scope covers this
	Project (FR-1.3) - never bypassed by an application-level filter."""
	user = user or frappe.session.user

	if "System Manager" in get_user_roles(user):
		return

	if not frappe.has_permission("Project", ptype=ptype, doc=project, user=user):
		log_security_event(
			"UNAUTHORIZED_PROJECT_ACCESS",
			{"user": user, "project": project, "ptype": ptype},
		)
		raise PermissionDeniedError(
			f"No {ptype} permission on Project {project}", error_code="PROJECT_SCOPE_DENIED"
		)


def assert_doc_permission(doctype: str, name: str | None = None, ptype: str = "read",
                           user: str | None = None):
	"""Assert frappe.has_permission on a specific document/doctype (the
	framework-native check NFR-SEC.1 requires before mutation)."""
	user = user or frappe.session.user
	if not frappe.has_permission(doctype, ptype=ptype, doc=name, user=user):
		log_security_event(
			"UNAUTHORIZED_DOC_ACCESS",
			{"user": user, "doctype": doctype, "name": name, "ptype": ptype},
		)
		raise PermissionDeniedError(
			f"No {ptype} permission on {doctype} {name or ''}".strip(),
			error_code="DOC_PERMISSION_DENIED",
		)


def get_assigned_projects(user: str | None = None) -> list[str]:
	"""Projects this user is scoped to via native User Permission (FR-1.3).
	A user with no restricting User Permission rows sees all Projects in
	their Company - that's Frappe's own semantics, not a BuildPolaris rule."""
	user = user or frappe.session.user
	rows = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": "Project"},
		fields=["for_value"],
		ignore_permissions=True,
	)
	return [r.for_value for r in rows]


def require_roles(*roles: str):
	"""Decorator form for api.py endpoints:

		@frappe.whitelist()
		@require_roles("BuildPolaris Project Manager", "BuildPolaris Admin")
		def create_commitment(...): ...
	"""
	def decorator(fn):
		def wrapper(*args, **kwargs):
			assert_role(*roles)
			return fn(*args, **kwargs)
		wrapper.__name__ = fn.__name__
		wrapper.__doc__ = fn.__doc__
		return wrapper
	return decorator
