from collections.abc import Mapping
from typing import Any

import httpx

from natalaibot.models import (
    GenerationLinkCreate,
    GenerationLinkRead,
    GenerationLinksPage,
    PersonCreate,
    PersonRead,
    PersonsPage,
)


class UsersAPIError(RuntimeError):
    """Raised when users/persons API returns an error response."""


class UsersClient:
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

    async def list_persons(self, telegram_id: int, limit: int = 5, offset: int = 0) -> PersonsPage:
        response = await self._client.get(
            f"/api/users/{telegram_id}/persons",
            params={"limit": limit, "offset": offset},
        )
        return PersonsPage.model_validate(self._parse_response(response))

    async def create_person(self, telegram_id: int, payload: PersonCreate) -> PersonRead:
        response = await self._client.post(
            f"/api/users/{telegram_id}/persons",
            json=payload.model_dump(mode="json"),
        )
        return PersonRead.model_validate(self._parse_response(response))

    async def get_person(self, telegram_id: int, person_id: str) -> PersonRead:
        response = await self._client.get(f"/api/users/{telegram_id}/persons/{person_id}")
        return PersonRead.model_validate(self._parse_response(response))

    async def delete_person(self, telegram_id: int, person_id: str) -> None:
        response = await self._client.delete(f"/api/users/{telegram_id}/persons/{person_id}")
        self._parse_response(response, allow_empty=True)

    async def create_generation_link(self, telegram_id: int, generation_id: str) -> GenerationLinkRead:
        response = await self._client.post(
            f"/api/users/{telegram_id}/generations",
            json=GenerationLinkCreate(generation_id=generation_id).model_dump(mode="json"),
        )
        return GenerationLinkRead.model_validate(self._parse_response(response))

    async def list_generation_links(self, telegram_id: int, limit: int = 5, offset: int = 0) -> GenerationLinksPage:
        response = await self._client.get(
            f"/api/users/{telegram_id}/generations",
            params={"limit": limit, "offset": offset},
        )
        return GenerationLinksPage.model_validate(self._parse_response(response))

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _parse_response(self, response: httpx.Response, allow_empty: bool = False) -> Any:
        if 200 <= response.status_code < 300:
            if allow_empty and not response.content:
                return None
            if response.status_code == 204:
                return None
            return response.json()

        raise UsersAPIError(_extract_error_detail(response))


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"Users service returned HTTP {response.status_code}"

    if isinstance(body, Mapping):
        detail = body.get("detail")
        if isinstance(detail, str):
            return detail
        if detail is not None:
            return str(detail)

    return f"Users service returned HTTP {response.status_code}"
