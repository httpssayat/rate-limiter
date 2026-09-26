import asyncio
import time

import httpx


def make_client(max_connections: int = 100) -> httpx.AsyncClient:
    limits = httpx.Limits(
        max_connections=max_connections,
        max_keepalive_connections=max_connections,
    )

    return httpx.AsyncClient(timeout=60, limits=limits)


async def wait_window_margin(
    window_seconds: int = 60,
    margin_seconds: float = 25,
) -> None:
    """
    Avoid starting strict limit tests too close to a window boundary.
    """
    position = time.time() % window_seconds

    if position > window_seconds - margin_seconds:
        await asyncio.sleep(window_seconds - position + 0.2)


async def post_check(
    client: httpx.AsyncClient,
    base_url: str,
    client_id: str,
) -> bool:
    try:
        response = await client.post(
            f"{base_url}/check",
            json={"client_id": client_id},
        )
        if response.status_code != 200:
            return False
        return response.json()["allowed"] is True
    except Exception:
        # Если соединение порвалось (ReadError), считаем запрос неуспешным
        return False


async def set_client_limit(
    client: httpx.AsyncClient,
    base_url: str,
    client_id: str,
    limit: int,
) -> None:
    response = await client.put(
        f"{base_url}/limits/{client_id}",
        json={"limit": limit},
    )

    assert response.status_code == 200