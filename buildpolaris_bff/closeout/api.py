"""Closeout - HTTP adapters only (NFR-MAINT.1)."""
import frappe

from buildpolaris_bff.shared.api_envelope import success
from buildpolaris_bff.closeout.services import (
	closeout_document_service,
	closeout_export_service,
	closeout_gate_service,
	closing_record_service,
	lien_waiver_service,
	substantial_completion_service,
)


@frappe.whitelist()
def open_closing_record(project):
	return success(closing_record_service.open_closing_record(project))


@frappe.whitelist()
def get_closing_record(project):
	return success(closing_record_service.get_closing_record(project))


@frappe.whitelist()
def get_retention_expiry(closing_record):
	return success(closing_record_service.get_retention_expiry(closing_record))


@frappe.whitelist()
def create_certificate(closing_record):
	return success(substantial_completion_service.create_certificate(closing_record))


@frappe.whitelist()
def sign_as_pm(certificate):
	return success(substantial_completion_service.sign_as_pm(certificate))


@frappe.whitelist()
def sign_as_owner(certificate):
	return success(substantial_completion_service.sign_as_owner(certificate))


@frappe.whitelist()
def record_architect_signoff(certificate, architect_name):
	return success(substantial_completion_service.record_architect_signoff(certificate, architect_name))


@frappe.whitelist()
def add_lien_waiver(closing_record, supplier, file, type, pay_application=None):
	return success(lien_waiver_service.add_lien_waiver(closing_record, supplier, file, type, pay_application))


@frappe.whitelist()
def list_lien_waivers(closing_record):
	return success(lien_waiver_service.list_lien_waivers(closing_record))


@frappe.whitelist()
def add_closeout_document(closing_record, category, file):
	return success(closeout_document_service.add_document(closing_record, category, file))


@frappe.whitelist()
def list_closeout_documents(closing_record):
	return success(closeout_document_service.list_documents(closing_record))


@frappe.whitelist()
def check_finalize_gate(closing_record):
	return success(closeout_gate_service.check_finalize_gate(closing_record))


@frappe.whitelist()
def finalize_closing_record(closing_record):
	return success(closeout_gate_service.finalize_closing_record(closing_record))


@frappe.whitelist()
def export_closeout_package(closing_record):
	return success(closeout_export_service.export_closeout_package(closing_record))
