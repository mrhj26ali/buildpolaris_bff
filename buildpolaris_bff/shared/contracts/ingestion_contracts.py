"""
Typed contract for the buildpolaris_bff <-> buildpolaris_ai document
ingestion boundary (FR-8.10, ARCH §4.2's "crosses a language runtime"
exception to the no-DTO rule).
"""
from dataclasses import dataclass


@dataclass
class IngestionRequest:
	file_id: str
	source_doctype: str
	source_name: str
	content_hash: str
	company: str
	project: str
	signed_file_reference: str
	trace_id: str


@dataclass
class IngestionResult:
	status: str  # "Indexed" | "Failed"
	chunk_count: int
	model_version: str
	status_detail: str | None = None
