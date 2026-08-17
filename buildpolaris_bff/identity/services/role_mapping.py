"""
Role name translation at the identity API boundary.

buildpolaris_pwa's FrappeRole type (src/types/domain.ts) uses short labels
('Admin', 'Project Manager', 'Site Superintendent', ...) throughout its UI
and wire contract. The actual Frappe Role records this app creates
(shared/permissions.PLATFORM_ROLES) are prefixed ('BuildPolaris Admin',
'BuildPolaris Project Manager', ...) so they're visibly distinct from any
other Frappe app's roles in the shared Role list.

This module is the ONE place that translates between them - every
identity/api.py function that sends or receives a role list does it
through here, so the short<->long mapping is never duplicated or drifted
across invite_user/update_user_roles/get_session_context/list_team_members.
"""
from buildpolaris_bff.shared.permissions import PLATFORM_ROLES

SHORT_TO_FRAPPE = {role.removeprefix("BuildPolaris "): role for role in PLATFORM_ROLES}
FRAPPE_TO_SHORT = {v: k for k, v in SHORT_TO_FRAPPE.items()}


def to_frappe_role(short_role: str) -> str:
	"""Raises KeyError-derived ValueError via the caller's own validation -
	deliberately does NOT swallow an unrecognized role, since silently
	dropping it would grant less access than the caller asked for without
	telling them."""
	if short_role in PLATFORM_ROLES:
		return short_role  # already a full Frappe Role name - tolerate both forms
	if short_role not in SHORT_TO_FRAPPE:
		raise ValueError(f"'{short_role}' is not a recognized BuildPolaris Role.")
	return SHORT_TO_FRAPPE[short_role]


def to_frappe_roles(short_roles: list[str]) -> list[str]:
	return [to_frappe_role(r) for r in short_roles]


def to_short_role(frappe_role: str) -> str | None:
	return FRAPPE_TO_SHORT.get(frappe_role)


def to_short_roles(frappe_roles: list[str]) -> list[str]:
	return [s for s in (to_short_role(r) for r in frappe_roles) if s is not None]
