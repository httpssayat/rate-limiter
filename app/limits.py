"""Manage per-client limits stored in Redis."""

from redis.asyncio import Redis

from .keys import limit_key


class ClientLimitService:
    """
    Reads and writes custom limits for clients.

    A limit is stored as a string integer in Redis.

    Example:
        rl:limit:{user_123} = "10"
    """

    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def set_limit(self, client_id: str, limit: int) -> None:
        """
        Set a custom limit for a client.

        limit = 0 means the client is blocked.
        """
        await self._redis.set(limit_key(client_id), limit)

    async def get_limit(self, client_id: str) -> int | None:
        """
        Get a custom limit for a client.

        Returns None if the client should use the default limit.
        """
        raw_value = await self._redis.get(limit_key(client_id))

        if raw_value is None:
            return None

        try:
            return int(raw_value)
        except ValueError:
            return None

    async def delete_limit(self, client_id: str) -> None:
        """
        Remove custom limit.

        After this the client will use the default limit.
        """
        await self._redis.delete(limit_key(client_id))