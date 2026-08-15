from frappe.model.document import Document


class AIDocumentIndex(Document):
	"""Status lives here in MariaDB, next to the File (ERD §3.6) - only the
	chunks/graph entries themselves live in buildpolaris_ai's Postgres.
	Never silent (NFR-AIGOV.3): every row terminates in Indexed or
	Failed(status_detail), visible to the uploading user's Role."""
	pass
