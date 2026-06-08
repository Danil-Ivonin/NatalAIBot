from collections.abc import Mapping
from typing import Any

import httpx

from natalaibot.models import GenerationCreate, GenerationCreated, GenerationRead, Character


class BackendAPIError(RuntimeError):
    """Raised when backend API returns an error response."""


class BackendClient:
    def __init__(
        self,
        base_url: str,
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            trust_env=False,
        )

    async def list_active_characters(self) -> list[Character]:
        response = await self._client.get("/api/v1/personas")
        data = self._parse_response(response)
        characters = [Character.model_validate(item) for item in data]
        return [character for character in characters if character.is_active]

    async def create_generation(self, payload: GenerationCreate) -> GenerationCreated:
        response = await self._client.post(
            "/api/v1/generations",
            json=payload.model_dump(mode="json"),
        )
        return GenerationCreated.model_validate(self._parse_response(response))

    async def get_generation(self, generation_id: str) -> GenerationRead:
        response = await self._client.get(f"/api/v1/generations/{generation_id}")
        return GenerationRead.model_validate(self._parse_response(response))

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _parse_response(self, response: httpx.Response) -> Any:
        if 200 <= response.status_code < 300:
            return response.json()

        detail = _extract_error_detail(response)
        raise BackendAPIError(detail)


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"Backend returned HTTP {response.status_code}"

    if isinstance(body, Mapping):
        detail = body.get("detail")
        if isinstance(detail, str):
            return detail
        if detail is not None:
            return str(detail)

    return f"Backend returned HTTP {response.status_code}"
