from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .limits import ClientLimitService
from .middleware import RateLimitMiddleware
from .rate_limiter import RateLimiter
from .redis_client import RedisService
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    redis_service = RedisService(settings)
    await redis_service.startup()

    limiter = RateLimiter(redis_service.client, settings)
    await limiter.startup()

    limits = ClientLimitService(redis_service.client)

    app.state.redis_service = redis_service
    app.state.limiter = limiter
    app.state.limits = limits

    try:
        yield
    finally:
        await redis_service.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Rate Limiter", lifespan=lifespan)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.include_router(router)

    return app


app = create_app()