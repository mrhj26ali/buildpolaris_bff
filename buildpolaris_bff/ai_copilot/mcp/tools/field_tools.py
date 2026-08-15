"""Read-only MCP tools over field/ (FR-8.4)."""
from buildpolaris_bff.field.services import punch_list_service, safety_incident_service


def get_open_punch_items(arguments: dict, asserted_user: str, asserted_project: str | None) -> dict:
	"""arguments: {"project": str}."""
	project = arguments.get("project") or asserted_project
	items = punch_list_service.list_punch_items(project, status="Open", user=asserted_user)
	return {"project": project, "punch_items": items}


def get_recent_safety_incidents(arguments: dict, asserted_user: str, asserted_project: str | None) -> dict:
	"""arguments: {"project": str}. Returns metadata only - the copilot's
	retrieval path for full incident narrative goes through document
	ingestion + citation (FR-8.3), never a raw dump of narrative/PII here."""
	project = arguments.get("project") or asserted_project
	incidents = safety_incident_service.list_incidents(project, user=asserted_user)
	return {"project": project, "incidents": incidents}
