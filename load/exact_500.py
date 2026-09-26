import asyncio
import os
import time
import uuid

import httpx

LB_URL = os.getenv("LB_URL", "http://localhost:8000")
TOTAL = int(os.getenv("TOTAL", "500"))
LIMIT = int(os.getenv("LIMIT", "100"))
WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))


async def wait_window_margin(window_seconds: int, margin_seconds: float = 25) -> None:
    position = time.time() % window_seconds

    if position > window_seconds - margin_seconds:
        await asyncio.sleep(window_seconds - position + 0.2)


async def warmup(client: httpx.AsyncClient) -> None:
    warmup_client_id = f"warmup-{uuid.uuid4().hex}"

    await asyncio.gather(
        *(
            client.post(f"{LB_URL}/check", json={"client_id": warmup_client_id})
            for _ in range(50)
        )
    )


async def main() -> None:
    limits = httpx.Limits(max_connections=1000, max_keepalive_connections=1000)

    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        await warmup(client)
        await wait_window_margin(WINDOW)

        client_id = f"load-{uuid.uuid4().hex}"

        async def one_request():
            start = time.perf_counter()

            response = await client.post(
                f"{LB_URL}/check",
                json={"client_id": client_id},
            )
            response.raise_for_status()

            allowed = response.json()["allowed"] is True
            latency = time.perf_counter() - start

            return allowed, latency

        started = time.perf_counter()
        results = await asyncio.gather(*(one_request() for _ in range(TOTAL)))
        duration = time.perf_counter() - started

    allowed_count = sum(1 for allowed, _ in results if allowed)
    latencies = sorted(latency for _, latency in results)

    def percentile(q: float) -> float:
        index = min(len(latencies) - 1, int(len(latencies) * q))
        return latencies[index]

    print(
        f"total={TOTAL} allowed={allowed_count} expected_allowed={LIMIT} "
        f"duration={duration:.3f}s"
    )

    print(
        f"p50={percentile(0.50) * 1000:.1f}ms "
        f"p95={percentile(0.95) * 1000:.1f}ms "
        f"p99={percentile(0.99) * 1000:.1f}ms"
    )

    if allowed_count != LIMIT:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())