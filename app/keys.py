"""Helpers for Redis key names.

All keys for one client use the same Redis hash tag: {client_id}.
This makes the keys compatible with Redis Cluster if we need it later.
"""


def counter_prefix(client_id: str) -> str:
    """
    Prefix for rate limit counter keys.

    Example:
        client_id = "user_123"
        result = "rl:{user_123}"

    Final counter key will look like:
        rl:{user_123}:12345
    """
    return f"rl:{{{client_id}}}"


def limit_key(client_id: str) -> str:
    """
    Key for a custom per-client limit.

    Example:
        client_id = "user_123"
        result = "rl:limit:{user_123}"
    """
    return f"rl:limit:{{{client_id}}}"