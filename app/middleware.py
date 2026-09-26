import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import Settings
from .rate_limiter import RateLimitState


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Protects demo endpoints with rate limiting.

    If the client exceeds the limit, returns 429 and rate limit headers.
    """

    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self._settings = settings

    def _sanitize_client_id(self, value: str) -> str:
        value = value.strip().replace("{", "").replace("}", "")
        return value or "unknown"

    def _client_id(self, request: Request) -> str:
        client_id = request.headers.get("x-client-id")

        if client_id:
            return self._sanitize_client_id(client_id)

        forwarded = request.headers.get("x-forwarded-for")

        if forwarded:
            first_ip = forwarded.split(",")[0].strip()
            return self._sanitize_client_id(first_ip)

        if request.client and request.client.host:
            return self._sanitize_client_id(request.client.host)

        return "unknown"

    def _protected(self, path: str) -> bool:
        return any(
            path.startswith(prefix)
            for prefix in self._settings.protected_path_prefixes
        )

    async def dispatch(self, request: Request, call_next):
        if not self._protected(request.url.path):
            return await call_next(request)

        limiter = getattr(request.app.state, "limiter", None)

        if limiter is None:
            return JSONResponse(
                status_code=503,
                content={"detail": "Rate limiter is not ready"},
                headers={"Retry-After": "1"},
            )

        client_id = self._client_id(request)
        result = await limiter.check(client_id)

        if result.state == RateLimitState.FAIL_CLOSED:
            return JSONResponse(
                status_code=503,
                content={"detail": "Rate limiter unavailable"},
                headers={"Retry-After": "1"},
            )

        retry_after = max(1, result.reset_at - int(time.time()))

        headers = {
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(max(0, result.remaining)),
            "X-RateLimit-Reset": str(result.reset_at),
        }

        if not result.allowed:
            headers["Retry-After"] = str(retry_after)

            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests"},
                headers=headers,
            )

        response = await call_next(request)

        for name, value in headers.items():
            response.headers[name] = value

        if result.state == RateLimitState.FAIL_OPEN:
            response.headers["X-RateLimit-Degraded"] = "true"

        return response