"""
FR-1.5: resolved session context (identity, Role, Company, assigned
Projects) in a single call for application bootstrap. This is what every
PWA feature slice's initial permission-gating reads from.
"""
import frappe

from buildpolaris_bff.shared.permissions import get_assigned_projects, get_user_roles


def get_session_context(user: str | None = None) -> dict:
	user = user or frappe.session.user

	if user == "Guest":
		return {"user": "Guest", "authenticated": False}

	user_doc = frappe.get_doc("User", user)
	company = getattr(user_doc, "bp_company", None)

	return {
		"user": user,
		"authenticated": True,
		"full_name": user_doc.full_name,
		"email": user_doc.email,
		"company": company,
		"roles": get_user_roles(user),
		"assigned_projects": get_assigned_projects(user),
	}
