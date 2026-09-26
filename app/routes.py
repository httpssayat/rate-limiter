import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from .limits import ClientLimitService
from .rate_limiter import RateLimiter
from .schemas import (
    CheckRequest,
    CheckResponse,
    ClientLimitResponse,
    SetClientLimitRequest,
    SetClientLimitResponse,
)

router = APIRouter()

_CLIENT_ID_PATTERN = re.compile(r"^[^{}\r\n]+$")


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.limiter


def get_limit_service(request: Request) -> ClientLimitService:
    return request.app.state.limits


def validate_client_id(client_id: str) -> None:
    """
    client_id is used inside Redis keys.

    We disallow empty values, very long values, and curly braces.
    Curly braces are reserved for Redis hash tags.
    """
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id must not be empty")

    if len(client_id) > 128:
        raise HTTPException(status_code=400, detail="client_id is too long")

    if not _CLIENT_ID_PATTERN.match(client_id):
        raise HTTPException(
            status_code=400,
            detail="client_id must not contain '{' or '}'",
        )


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.post("/check", response_model=CheckResponse)
async def check(
    payload: CheckRequest,
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    result = await limiter.check(payload.client_id)

    return CheckResponse(
        allowed=result.allowed,
        remaining=result.remaining,
        reset_at=result.reset_at,
    )


@router.get("/demo")
async def demo():
    return {"message": "demo endpoint"}


@router.get("/private/data")
async def private_data():
    return {"message": "private data"}


@router.put("/limits/{client_id}", response_model=SetClientLimitResponse)
async def set_client_limit(
    client_id: str,
    payload: SetClientLimitRequest,
    limits: ClientLimitService = Depends(get_limit_service),
):
    validate_client_id(client_id)

    await limits.set_limit(client_id, payload.limit)

    return SetClientLimitResponse(
        client_id=client_id,
        limit=payload.limit,
    )


@router.get("/limits/{client_id}", response_model=ClientLimitResponse)
async def get_client_limit(
    client_id: str,
    limits: ClientLimitService = Depends(get_limit_service),
):
    validate_client_id(client_id)

    limit = await limits.get_limit(client_id)

    return ClientLimitResponse(
        client_id=client_id,
        limit=limit,
    )


@router.delete("/limits/{client_id}", status_code=204)
async def delete_client_limit(
    client_id: str,
    limits: ClientLimitService = Depends(get_limit_service),
):
    validate_client_id(client_id)

    await limits.delete_limit(client_id)

    return Response(status_code=204)