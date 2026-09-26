import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

from .config import Settings


class RedisService:
    """
    Owns Redis connection pool and client lifecycle.

    The pool is created on application startup.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._pool: ConnectionPool | None = None
        self._client: redis.Redis | None = None

    async def startup(self) -> None:
        self._pool = ConnectionPool.from_url(
            self._settings.redis_url,
            max_connections=self._settings.redis_max_connections,
            socket_timeout=self._settings.redis_timeout_seconds,
            socket_connect_timeout=self._settings.redis_timeout_seconds,
            retry_on_timeout=False,
            health_check_interval=30,
            decode_responses=False,
        )
        self._client = redis.Redis(connection_pool=self._pool)

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Redis client is not initialized")
        return self._client

    async def shutdown(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass

        if self._pool is not None:
            try:
                await self._pool.disconnect()
            except Exception:
                pass