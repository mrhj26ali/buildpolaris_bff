"""
Typed contract for the copilot chat proxy (UC-8.1, ARCH §4.5's SSE proxy).
"""
from dataclasses import dataclass, field


@dataclass
class CopilotMessageRequest:
	thread_id: str | None
	message: str
	scope_assertion: str
	trace_id: str


@dataclass
class CitedClaim:
	text: str
	source_doctype: str
	source_name: str
	span_start: int
	span_end: int


@dataclass
class CopilotAnswer:
	answer_text: str
	citations: list = field(default_factory=list)
	is_refusal: bool = False
	model_version: str = ""
