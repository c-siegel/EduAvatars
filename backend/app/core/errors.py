"""
Domain Errors

Services raise these instead of FastAPI's HTTPException, so business logic doesn't depend on the
web framework. One exception handler (registered in app/main.py) turns them into the exact same
`{"detail": <ErrorCode>}` JSON body HTTPException produces, so clients can't tell the difference.

How to use:
    from app.core.errors import DomainError

    class LastAdminProtected(DomainError):
        status_code = 400
        detail = ErrorCode.LAST_ADMIN_PROTECTED

    raise LastAdminProtected()
"""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """A failure the client should see as a plain HTTP error with a stable error code."""

    status_code: int = 400
    detail: Any = None

    def __init__(self, detail: Any = None, status_code: int | None = None) -> None:
        if detail is not None:
            self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.detail)


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Render a DomainError the same way FastAPI renders an HTTPException."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
