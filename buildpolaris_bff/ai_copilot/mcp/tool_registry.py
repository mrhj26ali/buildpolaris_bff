"""
FR-8.4: one tool per platform read function, registered here. Adding a new
tool never means adding a new execution path - it's a thin wrapper over an
existing services/ function (NFR-EXT.3), same discipline as the
ActionApprovalGate on the write side.

Every tool function has the signature:
    fn(arguments: dict, asserted_user: str, asserted_project: str | None) -> dict
"""
from buildpolaris_bff.ai_copilot.mcp.tools import (
	communication_tools,
	field_tools,
	financial_tools,
	project_tools,
	scheduling_tools,
)

TOOLS = {
	"get_project_summary": {
		"fn": project_tools.get_project_summary,
		"description": "Cross-module dashboard summary for a Project (schedule health, open RFIs/submittals/punch items, CPI/SPI, next milestone).",
		"input_schema": {"type": "object", "properties": {"project": {"type": "string"}}, "required": ["project"]},
	},
	"get_schedule_state": {
		"fn": scheduling_tools.get_schedule_state,
		"description": "List a Project's Tasks with CPM outputs (critical path, float, dates).",
		"input_schema": {"type": "object", "properties": {"project": {"type": "string"}}, "required": ["project"]},
	},
	"get_lookahead": {
		"fn": scheduling_tools.get_lookahead,
		"description": "N-week look-ahead schedule for a Project.",
		"input_schema": {"type": "object", "properties": {
			"project": {"type": "string"}, "weeks": {"type": "integer"}, "as_of_date": {"type": "string"},
		}, "required": ["project"]},
	},
	"get_budget_summary": {
		"fn": financial_tools.get_budget_summary,
		"description": "Budget vs. committed vs. actual per Cost Code on a Project.",
		"input_schema": {"type": "object", "properties": {"project": {"type": "string"}}, "required": ["project"]},
	},
	"get_evm_summary": {
		"fn": financial_tools.get_evm_summary,
		"description": "Earned Value Management snapshot (CPI/SPI) for a Project, as of an optional date.",
		"input_schema": {"type": "object", "properties": {
			"project": {"type": "string"}, "as_of_date": {"type": "string"},
		}, "required": ["project"]},
	},
	"get_rfi_status": {
		"fn": communication_tools.get_rfi_status,
		"description": "List a Project's RFIs with status, assignee, due date.",
		"input_schema": {"type": "object", "properties": {"project": {"type": "string"}}, "required": ["project"]},
	},
	"get_open_action_items": {
		"fn": communication_tools.get_open_action_items,
		"description": "List a Project's open meeting Action Items.",
		"input_schema": {"type": "object", "properties": {"project": {"type": "string"}}, "required": ["project"]},
	},
	"get_open_punch_items": {
		"fn": field_tools.get_open_punch_items,
		"description": "List a Project's open Punch List items.",
		"input_schema": {"type": "object", "properties": {"project": {"type": "string"}}, "required": ["project"]},
	},
	"get_recent_safety_incidents": {
		"fn": field_tools.get_recent_safety_incidents,
		"description": "List a Project's Safety Incidents (metadata only - severity, date, status).",
		"input_schema": {"type": "object", "properties": {"project": {"type": "string"}}, "required": ["project"]},
	},
}


def list_tools() -> list:
	return [{"name": name, "description": spec["description"], "input_schema": spec["input_schema"]}
	        for name, spec in TOOLS.items()]


def get_tool(name: str):
	spec = TOOLS.get(name)
	return spec["fn"] if spec else None
