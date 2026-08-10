import frappe
from buildpolaris_bff.document_control.services import drawing, revision, annotation

@frappe.whitelist()
def get_drawing_register(project: str): return frappe.get_all("Drawing", filters={"project": project, "status": "Active"})
@frappe.whitelist()
def create_drawing(**kwargs): return drawing.create_drawing(**kwargs)
@frappe.whitelist()
def create_revision(**kwargs): return revision.create_revision(**kwargs)
@frappe.whitelist()
def promote_to_shared(revision_id: str): return revision.promote_to_shared(revision_id)
@frappe.whitelist()
def publish_revision(revision_id: str, authorized_by: str = None): return revision.publish_revision(revision_id, authorized_by)
