"""Read-only MCP tools over financials/ (FR-8.4)."""
from buildpolaris_bff.financials.services import cost_code_service, evm_service


def get_budget_summary(arguments: dict, asserted_user: str, asserted_project: str | None) -> dict:
	"""Budget vs. committed vs. actual per Cost Code. arguments: {"project": str}.
	Field-level masking for Subcontractor is enforced natively via permlevel
	on the underlying doctypes - this tool never bypasses it."""
	project = arguments.get("project") or asserted_project
	rollup = cost_code_service.get_budget_rollup(project, user=asserted_user)
	return {"project": project, "rollup": rollup}


def get_evm_summary(arguments: dict, asserted_user: str, asserted_project: str | None) -> dict:
	"""arguments: {"project": str, "as_of_date": str|None}."""
	project = arguments.get("project") or asserted_project
	as_of_date = arguments.get("as_of_date")
	return evm_service.compute_evm(project, as_of_date, user=asserted_user)
