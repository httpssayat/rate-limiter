import asyncio
import uuid

from env import APP1_URL, APP2_URL, LB_URL
from helpers import (
    make_client,
    post_check,
    set_client_limit,
    wait_window_margin,
)


async def test_custom_limit_overrides_default():
    await wait_window_margin(60, 25)

    client_id = f"custom-{uuid.uuid4().hex}"

    async with make_client(10) as client:
        await set_client_limit(client, LB_URL, client_id, 5)

        results = await asyncio.gather(
            *(
                post_check(client, LB_URL, client_id)
                for _ in range(6)
            )
        )

    assert sum(results) == 5


async def test_default_limit_is_used_when_no_custom_limit():
    client_id = f"default-{uuid.uuid4().hex}"

    async with make_client(10) as client:
        results = await asyncio.gather(
            *(
                post_check(client, LB_URL, client_id)
                for _ in range(6)
            )
        )

    assert sum(results) == 6


async def test_zero_limit_blocks_client():
    client_id = f"zero-{uuid.uuid4().hex}"

    async with make_client(5) as client:
        await set_client_limit(client, LB_URL, client_id, 0)

        results = await asyncio.gather(
            *(
                post_check(client, LB_URL, client_id)
                for _ in range(3)
            )
        )

    assert sum(results) == 0


async def test_lowering_limit_blocks_client():
    await wait_window_margin(60, 25)

    client_id = f"lower-{uuid.uuid4().hex}"

    async with make_client(5) as client:
        await set_client_limit(client, LB_URL, client_id, 3)

        first_results = await asyncio.gather(
            *(
                post_check(client, LB_URL, client_id)
                for _ in range(3)
            )
        )

        assert sum(first_results) == 3

        await set_client_limit(client, LB_URL, client_id, 1)

        next_allowed = await post_check(client, LB_URL, client_id)

    assert next_allowed is False


async def test_custom_limit_is_shared_between_instances():
    await wait_window_margin(60, 25)

    client_id = f"shared-custom-{uuid.uuid4().hex}"

    async with make_client(10) as client:
        await set_client_limit(client, LB_URL, client_id, 5)

        async def send_requests(base_url: str, count: int) -> int:
            results = await asyncio.gather(
                *(
                    post_check(client, base_url, client_id)
                    for _ in range(count)
                )
            )
            return sum(results)

        allowed_app1, allowed_app2 = await asyncio.gather(
            send_requests(APP1_URL, 3),
            send_requests(APP2_URL, 3),
        )

    assert allowed_app1 + allowed_app2 == 5


async def test_get_and_delete_limit():
    client_id = f"limit-management-{uuid.uuid4().hex}"

    async with make_client(2) as client:
        await set_client_limit(client, LB_URL, client_id, 7)

        response = await client.get(f"{LB_URL}/limits/{client_id}")
        assert response.status_code == 200
        assert response.json()["limit"] == 7

        response = await client.delete(f"{LB_URL}/limits/{client_id}")
        assert response.status_code == 204

        response = await client.get(f"{LB_URL}/limits/{client_id}")
        assert response.status_code == 200
        assert response.json()["limit"] is None