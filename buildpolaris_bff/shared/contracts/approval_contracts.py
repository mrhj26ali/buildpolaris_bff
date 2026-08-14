"""
Typed contract for FR-8.6's gated write proposals - the one shared shape
every agent (RFI drafting, contract-clause, submittal review, ...) uses to
propose a write, per NFR-EXT.3 ("no feature builds its own copy").
"""
from dataclasses import dataclass


@dataclass
class ProposedActionPayload:
	agent_type: str
	target_doctype: str
	proposed_payload: dict
	model_version: str
	confidence: float
	tool_trace_id: str
	idempotency_key: str


@dataclass
class ApprovalDecision:
	approval_name: str
	decision: str  # "Approved" | "Rejected"
	approver: str
	decided_at: str | None = None
