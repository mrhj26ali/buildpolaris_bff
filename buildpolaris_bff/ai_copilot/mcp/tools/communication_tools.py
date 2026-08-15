"""Read-only MCP tools over communications/ (FR-8.4)."""
from buildpolaris_bff.communications.services import rfi_service, action_item_service


def get_rfi_status(arguments: dict, asserted_user: str, asserted_project: str | None) -> dict:
	"""arguments: {"project": str}."""
	project = arguments.get("project") or asserted_project
	rfis = rfi_service.list_rfis(project, user=asserted_user)
	return {"project": project, "rfis": rfis}


def get_open_action_items(arguments: dict, asserted_user: str, asserted_project: str | None) -> dict:
	"""arguments: {"project": str}."""
	project = arguments.get("project") or asserted_project
	items = action_item_service.list_action_items(project, status="Open", user=asserted_user)
	return {"project": project, "action_items": items}
