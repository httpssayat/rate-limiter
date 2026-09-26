from pydantic import BaseModel, Field


MAX_CLIENT_LIMIT = 100_000

CLIENT_ID_PATTERN = r"^[^{}\r\n]+$"


class CheckRequest(BaseModel):
    client_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=CLIENT_ID_PATTERN,
    )


class CheckResponse(BaseModel):
    allowed: bool
    remaining: int
    reset_at: int


class SetClientLimitRequest(BaseModel):
    limit: int = Field(
        ge=0,
        le=MAX_CLIENT_LIMIT,
        description="0 fully blocks the client",
    )


class SetClientLimitResponse(BaseModel):
    client_id: str
    limit: int


class ClientLimitResponse(BaseModel):
    client_id: str
    limit: int | None