"""Closeout - HTTP adapters only (NFR-MAINT.1)."""
import frappe

from buildpolaris_bff.shared.api_envelope import success, api_guard
from buildpolaris_bff.closeout.services import (
	closeout_document_service,
	closeout_export_service,
	closeout_gate_service,
	closing_record_service,
	lien_waiver_service,
	substantial_completion_service,
)


@frappe.whitelist()
@api_guard
def open_closing_record(project):
	return success(closing_record_service.open_closing_record(project))


@frappe.whitelist()
@api_guard
def get_closing_record(project):
	return success(closing_record_service.get_closing_record(project))


@frappe.whitelist()
@api_guard
def get_retention_expiry(closing_record):
	return success(closing_record_service.get_retention_expiry(closing_record))


@frappe.whitelist()
@api_guard
def create_certificate(closing_record):
	return success(substantial_completion_service.create_certificate(closing_record))


@frappe.whitelist()
@api_guard
def sign_as_pm(certificate):
	return success(substantial_completion_service.sign_as_pm(certificate))


@frappe.whitelist()
@api_guard
def sign_as_owner(certificate):
	return success(substantial_completion_service.sign_as_owner(certificate))


@frappe.whitelist()
@api_guard
def record_architect_signoff(certificate, architect_name):
	return success(substantial_completion_service.record_architect_signoff(certificate, architect_name))


@frappe.whitelist()
@api_guard
def add_lien_waiver(closing_record, supplier, file, type, pay_application=None):
	return success(lien_waiver_service.add_lien_waiver(closing_record, supplier, file, type, pay_application))


@frappe.whitelist()
@api_guard
def list_lien_waivers(closing_record):
	return success(lien_waiver_service.list_lien_waivers(closing_record))


@frappe.whitelist()
@api_guard
def add_closeout_document(closing_record, category, file):
	return success(closeout_document_service.add_document(closing_record, category, file))


@frappe.whitelist()
@api_guard
def list_closeout_documents(closing_record):
	return success(closeout_document_service.list_documents(closing_record))


@frappe.whitelist()
@api_guard
def check_finalize_gate(closing_record):
	return success(closeout_gate_service.check_finalize_gate(closing_record))


@frappe.whitelist()
@api_guard
def finalize_closing_record(closing_record):
	return success(closeout_gate_service.finalize_closing_record(closing_record))


@frappe.whitelist()
@api_guard
def export_closeout_package(closing_record):
	return success(closeout_export_service.export_closeout_package(closing_record))
@frappe.whitelist()
@api_guard
def get_substantial_completion(closing_record):
    """Fetch the Substantial Completion Certificate by its parent Closing Record."""
    cert_name = frappe.db.get_value("Substantial Completion Certificate", {"closing_record": closing_record}, "name")
    if not cert_name:
        return success(None)
    return success(frappe.get_doc("Substantial Completion Certificate", cert_name).as_dict())

@frappe.whitelist()
@api_guard
def sign_substantial_completion(closing_record, signoff_role):
    """Unified sign-off endpoint routed to the correct service based on role."""
    cert_name = frappe.db.get_value("Substantial Completion Certificate", {"closing_record": closing_record}, "name")
    if not cert_name:
        frappe.throw("No Substantial Completion Certificate found for this Closing Record.", frappe.DoesNotExistError)
    
    if signoff_role == "pm":
        return success(substantial_completion_service.sign_as_pm(cert_name))
    elif signoff_role == "owner":
        return success(substantial_completion_service.sign_as_owner(cert_name))
    elif signoff_role == "architect":
        # Defaulting architect name if not provided by the PWA payload
        return success(substantial_completion_service.record_architect_signoff(cert_name, architect_name="Architect of Record"))
    else:
        frappe.throw("Invalid signoff_role. Must be 'pm', 'owner', or 'architect'.")