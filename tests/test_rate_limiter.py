import asyncio
import uuid

import httpx
import pytest

from env import APP1_URL, APP2_URL, APP_SHORT_URL, LB_URL, REDIS_URL
from helpers import make_client, post_check, wait_window_margin


async def test_500_parallel_one_client_exact_100_allowed():
    await wait_window_margin(60, 25)

    client_id = f"acceptance-{uuid.uuid4().hex}"
    total = 500

    async with make_client(total) as client:
        results = await asyncio.gather(
            *(
                post_check(client, LB_URL, client_id)
                for _ in range(total)
            )
        )

    assert sum(results) == 100


async def test_clients_are_isolated():
    await wait_window_margin(60, 25)

    client_1 = f"iso-1-{uuid.uuid4().hex}"
    client_2 = f"iso-2-{uuid.uuid4().hex}"

    per_client = 120

    async with make_client(per_client * 2) as client:
        async def run_for(client_id: str) -> int:
            results = await asyncio.gather(
                *(
                    post_check(client, LB_URL, client_id)
                    for _ in range(per_client)
                )
            )
            return sum(results)

        allowed_1, allowed_2 = await asyncio.gather(
            run_for(client_1),
            run_for(client_2),
        )

    assert allowed_1 == 100
    assert allowed_2 == 100


async def test_both_instances_share_state():
    await wait_window_margin(60, 25)

    client_id = f"two-instances-{uuid.uuid4().hex}"
    per_instance = 60

    async with make_client(per_instance * 2) as client:
        async def run_for(base_url: str) -> int:
            results = await asyncio.gather(
                *(
                    post_check(client, base_url, client_id)
                    for _ in range(per_instance)
                )
            )
            return sum(results)

        allowed_1, allowed_2 = await asyncio.gather(
            run_for(APP1_URL),
            run_for(APP2_URL),
        )

    assert allowed_1 + allowed_2 == 100


async def test_middleware_returns_429_with_headers():
    await wait_window_margin(60, 25)

    client_id = f"demo-{uuid.uuid4().hex}"
    headers = {"X-Client-ID": client_id}

    total = 100

    async with make_client(total + 5) as client:
        responses = await asyncio.gather(
            *(
                client.get(f"{LB_URL}/demo", headers=headers)
                for _ in range(total)
            )
        )

        assert all(response.status_code == 200 for response in responses)

        blocked = await client.get(f"{LB_URL}/demo", headers=headers)

    assert blocked.status_code == 429
    assert blocked.headers["x-ratelimit-limit"] == "100"
    assert blocked.headers["x-ratelimit-remaining"] == "0"
    assert "x-ratelimit-reset" in blocked.headers
    assert "retry-after" in blocked.headers


async def test_redis_key_has_ttl():
    client_id = f"ttl-{uuid.uuid4().hex}"

    async with make_client(1) as client:
        response = await client.post(
            f"{LB_URL}/check",
            json={"client_id": client_id},
        )

        assert response.status_code == 200
        data = response.json()

    import redis.asyncio as redis

    redis_client = redis.from_url(REDIS_URL, decode_responses=True)

    try:
        window = 60
        bucket = data["reset_at"] // window - 1
        key = f"rl:{{{client_id}}}:{bucket}"

        ttl = await redis_client.ttl(key)

        assert 0 < ttl <= window + 1
    finally:
        await redis_client.aclose()


@pytest.mark.skipif(not APP_SHORT_URL, reason="APP_SHORT_URL is not set")
async def test_window_reset_after_window_end():
    await wait_window_margin(2, 1.5)

    client_id = f"reset-{uuid.uuid4().hex}"

    async with httpx.AsyncClient(timeout=10) as client:
        for _ in range(5):
            response = await client.post(
                f"{APP_SHORT_URL}/check",
                json={"client_id": client_id},
            )
            assert response.json()["allowed"] is True

        response = await client.post(
            f"{APP_SHORT_URL}/check",
            json={"client_id": client_id},
        )
        assert response.json()["allowed"] is False

        await asyncio.sleep(2.3)

        response = await client.post(
            f"{APP_SHORT_URL}/check",
            json={"client_id": client_id},
        )
        assert response.json()["allowed"] is True