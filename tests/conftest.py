import asyncio

import httpx
import pytest

from env import APP1_URL, APP2_URL, APP_SHORT_URL, LB_URL


@pytest.fixture(scope="session", autouse=True)
def wait_services():
    async def _wait():
        urls = [LB_URL, APP1_URL, APP2_URL]

        if APP_SHORT_URL:
            urls.append(APP_SHORT_URL)

        async with httpx.AsyncClient(timeout=2) as client:
            loop = asyncio.get_running_loop()

            for url in urls:
                deadline = loop.time() + 90

                while True:
                    try:
                        response = await client.get(url + "/healthz")
                        if response.status_code == 200:
                            break
                    except Exception:
                        pass

                    if loop.time() > deadline:
                        raise RuntimeError(f"Service {url} is not ready")

                    await asyncio.sleep(0.5)

    asyncio.run(_wait())