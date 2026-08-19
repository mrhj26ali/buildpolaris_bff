"""
FR-1.5: resolved session context (identity, Role, Company, assigned
Projects) in a single call for application bootstrap. This is what every
PWA feature slice's initial permission-gating reads from.

Wire contract matches buildpolaris_pwa/src/types/domain.ts's
SessionContext exactly: {email, full_name, roles, company, is_admin,
projects} - roles in SHORT form (role_mapping.py), projects as
{name, title} objects (Project.name is an opaque naming-series value
since patches/v1_0/fix_project_naming.py, so the human-readable
project_name has to be resolved and shipped separately).

Deliberately has no Guest/"authenticated" branch: get_session_context is
NOT allow_guest, so Frappe's own @frappe.whitelist() already rejects an
unauthenticated caller with a 401 before this function body ever runs -
buildpolaris_pwa's useAuth.ts already treats exactly that (a BffApiError
with status 401) as "not logged in", not a field in a 200 response.
"""
import frappe

from buildpolaris_bff.identity.services.role_mapping import to_short_roles
from buildpolaris_bff.shared.permissions import get_user_roles


def get_session_context(user: str | None = None) -> dict:
	user = user or frappe.session.user

	user_doc = frappe.get_doc("User", user)
	company = getattr(user_doc, "bp_company", None)
	frappe_roles = get_user_roles(user)

	return {
		"email": user_doc.email,
		"full_name": user_doc.full_name,
		"roles": to_short_roles(frappe_roles),
		"company": company,
		"is_admin": "BuildPolaris Admin" in frappe_roles,
		"projects": _assigned_projects_with_titles(user),
	}


def _assigned_projects_with_titles(user: str) -> list:
	# Reuses projects/services/project_service.list_projects() rather than
	# re-deriving "which Projects can this user see" a second time -
	# that function already implements the exact semantics documented in
	# shared/permissions.get_assigned_projects(): every Project in the
	# user's Company by default, narrowed by an explicit User Permission
	# row only when one exists.
	from buildpolaris_bff.bp_projects.services.project_service import list_projects

	try:
		rows = list_projects(user=user)
	except Exception:
		return []
	return [{"name": r["name"], "title": r["project_name"]} for r in rows]
