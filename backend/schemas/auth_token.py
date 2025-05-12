from pydantic import BaseModel


class AuthToken(BaseModel):
    access_token: str
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str


class AuthTokenData(BaseModel):
    username: str | None = None
