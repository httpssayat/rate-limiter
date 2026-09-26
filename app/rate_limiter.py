import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from redis.asyncio import Redis
from redis.exceptions import RedisError

from .config import Settings
from .keys import counter_prefix, limit_key

logger = logging.getLogger(__name__)

_SCRIPT_PATH = Path(__file__).parent / "lua" / "rate_limit.lua"


class RateLimitState(str, Enum):
    OK = "ok"
    LIMITED = "limited"
    FAIL_OPEN = "fail_open"
    FAIL_CLOSED = "fail_closed"


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_at: int
    current: int
    limit: int
    state: RateLimitState


def _next_local_reset(window_seconds: int) -> int:
    """
    Used only when Redis is unavailable.

    We cannot use Redis time in this case, so we use local time.
    """
    now = int(time.time())
    return (now // window_seconds + 1) * window_seconds


class RateLimiter:
    """
    Checks fixed-window rate limits in Redis.

    The actual check is performed by a Lua script inside Redis.
    This makes the check atomic.
    """

    def __init__(self, redis_client: Redis, settings: Settings) -> None:
        self._redis = redis_client
        self._settings = settings
        self._script = None

    async def startup(self) -> None:
        """
        Register the Lua script in Redis client.

        This does not require Redis to be available right now.
        The script will be sent later during the first real call.
        """
        script_text = _SCRIPT_PATH.read_text(encoding="utf-8")
        self._script = self._redis.register_script(script_text)

    async def check(self, client_id: str) -> RateLimitResult:
        """
        Check whether the client is allowed to make a request.
        """
        if self._script is None:
            await self.startup()

        keys = [
            counter_prefix(client_id),
            limit_key(client_id),
        ]

        args = [
            self._settings.rate_limit_limit,
            self._settings.rate_limit_window_seconds,
        ]

        try:
            raw_result = await self._script(keys=keys, args=args)
            return self._parse_result(raw_result)
        except (RedisError, TimeoutError, OSError) as exc:
            logger.warning(
                "Rate limit check failed for client_id=%s: %s",
                client_id,
                exc,
            )
            return self._degraded_result()

    def _parse_result(self, raw_result) -> RateLimitResult:
        """
        Convert Redis Lua result into a Python object.
        """
        (
            allowed_raw,
            remaining_raw,
            reset_raw,
            current_raw,
            limit_raw,
        ) = raw_result

        allowed = int(allowed_raw) == 1

        state = RateLimitState.OK if allowed else RateLimitState.LIMITED

        return RateLimitResult(
            allowed=allowed,
            remaining=int(remaining_raw),
            reset_at=int(reset_raw),
            current=int(current_raw),
            limit=int(limit_raw),
            state=state,
        )

    def _degraded_result(self) -> RateLimitResult:
        """
        Result used when Redis is unavailable.

        Behaviour depends on RATE_LIMIT_FAIL_OPEN setting.
        """
        reset_at = _next_local_reset(self._settings.rate_limit_window_seconds)
        limit = self._settings.rate_limit_limit

        if self._settings.rate_limit_fail_open:
            return RateLimitResult(
                allowed=True,
                remaining=limit,
                reset_at=reset_at,
                current=0,
                limit=limit,
                state=RateLimitState.FAIL_OPEN,
            )

        return RateLimitResult(
            allowed=False,
            remaining=0,
            reset_at=reset_at,
            current=0,
            limit=limit,
            state=RateLimitState.FAIL_CLOSED,
        )