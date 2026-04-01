"""
Permission-aware auth middleware.

Extracts the Bearer token from the Authorization header, validates it, and
attaches identity to request.state:
  - request.state.user_id: str
  - request.state.authorized_project_keys: list[str]  (empty = all projects)

For MVP internal tooling the token is treated as an opaque user ID and all
projects are authorized. Plug in a real identity provider by replacing
_resolve_identity().
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.logging_config import get_logger

logger = get_logger(__name__)

# Paths that bypass auth (health probes, etc.)
_PUBLIC_PATHS: frozenset[str] = frozenset({"/", "/health", "/docs", "/openapi.json", "/redoc"})


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _PUBLIC_PATHS:
            request.state.user_id = "anonymous"
            request.state.authorized_project_keys = []
            request.state.project_keys = []
            request.state.is_admin = False
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header. Expected: Bearer <token>"},
            )

        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Empty bearer token."})

        user_id, authorized_project_keys, is_admin = _resolve_identity(token)
        request.state.user_id = user_id
        request.state.authorized_project_keys = authorized_project_keys
        # Expose on request.state as both names for compatibility
        request.state.project_keys = authorized_project_keys
        request.state.is_admin = is_admin

        logger.debug("Authenticated request", extra={"user_id": user_id, "path": request.url.path})
        return await call_next(request)


def _resolve_identity(token: str) -> tuple[str, list[str], bool]:
    """
    Resolve a bearer token to (user_id, authorized_project_keys, is_admin).

    MVP implementation: treats the token as the user ID and grants access to
    all projects (empty list = no restriction).  Tokens prefixed with "admin-"
    are granted admin rights for the audit endpoint.  Replace with a call to
    your organization's identity provider.
    """
    is_admin = token.startswith("admin-")
    return token, [], is_admin


def is_project_authorized(request: Request, project_key: str) -> bool:
    """
    Return True if the authenticated user can access the given Jira project key.

    An empty authorized_project_keys list means all projects are accessible
    (MVP default). A non-empty list restricts access to those keys only.
    """
    authorized: list[str] = getattr(request.state, "authorized_project_keys", [])
    if not authorized:
        return True
    return project_key in authorized
