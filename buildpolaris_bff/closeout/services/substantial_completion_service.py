"""FR-7.2: Substantial Completion Certificate requiring PM, Owner, and
Architect sign-off. Once all three are present, promotes the Closing
Record to SubstantiallyComplete."""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def create_certificate(closing_record: str, created_by: str | None = None):
	created_by = created_by or frappe.session.user
	closing_doc = frappe.get_doc("Closing Record", closing_record)
	assert_project_permission(closing_doc.project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	if frappe.db.exists("Substantial Completion Certificate", {"closing_record": closing_record}):
		raise ValidationError("A Substantial Completion Certificate already exists for this Closing Record.")

	doc = frappe.get_doc({
		"doctype": "Substantial Completion Certificate",
		"naming_series": "SCC-.YYYY.-.#####",
		"closing_record": closing_record,
	})
	doc.insert()
	return doc.as_dict()


def sign_as_pm(certificate: str, signer: str | None = None):
	signer = signer or frappe.session.user
	doc = frappe.get_doc("Substantial Completion Certificate", certificate)
	closing_doc = frappe.get_doc("Closing Record", doc.closing_record)
	assert_project_permission(closing_doc.project, ptype="write", user=signer)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=signer)

	doc.pm_signoff = signer
	doc.save()
	_promote_if_complete(doc)
	return doc.as_dict()


def sign_as_owner(certificate: str, signer: str | None = None):
	signer = signer or frappe.session.user
	doc = frappe.get_doc("Substantial Completion Certificate", certificate)
	closing_doc = frappe.get_doc("Closing Record", doc.closing_record)
	assert_project_permission(closing_doc.project, ptype="write", user=signer)
	assert_role("BuildPolaris Owner", "BuildPolaris Admin", user=signer)

	doc.owner_signoff = signer
	doc.save()
	_promote_if_complete(doc)
	return doc.as_dict()


def record_architect_signoff(certificate: str, architect_name: str, recorded_by: str | None = None):
	"""The Architect of Record is typically not a platform User (ERD §3.5:
	free-text field) - a PM or Owner records the name on their behalf."""
	recorded_by = recorded_by or frappe.session.user
	doc = frappe.get_doc("Substantial Completion Certificate", certificate)
	closing_doc = frappe.get_doc("Closing Record", doc.closing_record)
	assert_project_permission(closing_doc.project, ptype="write", user=recorded_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Owner", "BuildPolaris Admin", user=recorded_by)

	doc.architect_signoff = architect_name
	doc.save()
	_promote_if_complete(doc)
	return doc.as_dict()


def _promote_if_complete(certificate_doc):
	"""Once all three sign-offs are present (signed_at auto-set by the
	controller's validate()), promote the parent Closing Record."""
	if certificate_doc.signed_at:
		closing_doc = frappe.get_doc("Closing Record", certificate_doc.closing_record)
		if closing_doc.status == "Open":
			closing_doc.status = "SubstantiallyComplete"
			closing_doc.save()
