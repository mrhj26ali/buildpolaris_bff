"""
BuildPolaris shared exception types.

Every service-layer function should raise one of these rather than a bare
frappe.throw(), so api.py's error envelope (shared/api_envelope.py) can map
exceptions to a consistent wire-format without each api.py function needing
its own try/except boilerplate (NFR-MAINT.1: api.py stays thin).
"""
import frappe


class BuildPolarisError(Exception):
	"""Base class for all BuildPolaris-raised, expected errors."""
	http_status_code = 500
	error_code = "BP_ERROR"

	def __init__(self, message: str, error_code: str | None = None):
		super().__init__(message)
		self.message = message
		if error_code:
			self.error_code = error_code


class PermissionDeniedError(BuildPolarisError):
	"""Raised when NFR-SEC.1's Role/permission assertion fails."""
	http_status_code = 403
	error_code = "PERMISSION_DENIED"


class ValidationError(BuildPolarisError):
	"""Raised for request-shape or business-rule validation failures."""
	http_status_code = 400
	error_code = "VALIDATION_ERROR"


class NotFoundError(BuildPolarisError):
	http_status_code = 404
	error_code = "NOT_FOUND"


class IdempotencyConflictError(BuildPolarisError):
	"""Raised when a replayed write's payload doesn't match the original
	(NFR-SCALE.6) - the key was reused for a different request body."""
	http_status_code = 409
	error_code = "IDEMPOTENCY_CONFLICT"


class ScopeAssertionError(BuildPolarisError):
	"""Raised when minting or verifying a BFF<->AI Scope Assertion fails
	(ARCH §4.2)."""
	http_status_code = 401
	error_code = "SCOPE_ASSERTION_ERROR"


class RateLimitedError(BuildPolarisError):
	http_status_code = 429
	error_code = "RATE_LIMITED"


class CloseoutGateError(BuildPolarisError):
	"""Raised when a closeout-gate invariant (FR-7.5) blocks a transition."""
	http_status_code = 409
	error_code = "CLOSEOUT_GATE_BLOCKED"


class ImmutableRecordError(BuildPolarisError):
	"""Raised when a write targets a record that is immutable post-approval
	(FR-3.8, NFR-AUD.1) outside the defined amendment flow."""
	http_status_code = 409
	error_code = "IMMUTABLE_RECORD"


class AISidecarUnavailableError(BuildPolarisError):
	"""Raised when buildpolaris_ai is slow, unreachable, or returns an
	unexpected response. NFR-SCALE.5: the platform must remain fully usable
	for all non-AI workflows when this happens - callers of this exception
	(copilot_gateway_service, ingestion_trigger_service) must fail closed
	with a clear message, never block or corrupt a core PM workflow."""
	http_status_code = 503
	error_code = "AI_SIDECAR_UNAVAILABLE"


def to_frappe_exception(err: BuildPolarisError):
	"""Translate a BuildPolarisError into the nearest native frappe exception
	so Frappe's own request/response machinery sets the right HTTP status."""
	if isinstance(err, PermissionDeniedError):
		return frappe.PermissionError(err.message)
	if isinstance(err, NotFoundError):
		return frappe.DoesNotExistError(err.message)
	if isinstance(err, RateLimitedError):
		return frappe.exceptions.TooManyRequestsError(err.message)
	return frappe.ValidationError(err.message)
