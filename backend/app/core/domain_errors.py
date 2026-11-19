"""Domain/service-layer errors mapped to API responses by routers.

These represent expected business failures (not bugs). The global error handler
must continue to sanitize unexpected exceptions; routers should translate these
into explicit HTTP status codes without leaking internals.
"""


class DomainError(ValueError):
    """Base class for expected domain/business rule failures."""


class NotFoundError(DomainError):
    """A requested entity does not exist in the caller's tenant scope."""


class ConflictError(DomainError):
    """The request conflicts with current state (e.g. insufficient stock)."""


class ValidationError(DomainError):
    """The request is semantically invalid for the current business operation."""
