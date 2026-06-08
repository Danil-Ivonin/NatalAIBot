import httpx
import pytest

from natalaibot.http import backend_client
from natalaibot.http.backend_client import BackendAPIError, BackendClient
from natalaibot.models import GenerationCreate, GeoPoint


def test_backend_client_ignores_environment_proxy_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_kwargs: dict[str, object] = {}

    class SpyAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            captured_kwargs.update(kwargs)

    monkeypatch.setattr(backend_client.httpx, "AsyncClient", SpyAsyncClient)

    BackendClient(base_url="http://localhost:8000")

    assert captured_kwargs["trust_env"] is False


@pytest.mark.asyncio
async def test_list_characters_returns_active_characters() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/personas"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "22222222-2222-4222-8222-222222222222",
                    "name": "Roast Persona",
                    "slug": "roast-persona",
                    "description": "Sharp report style.",
                    "is_active": True,
                    "created_at": "2026-05-17T10:00:00Z",
                    "updated_at": "2026-05-17T10:00:00Z",
                    "style_profile": None,
                    "quotes": [],
                    "phrase_templates": [],
                    "style_examples": [],
                },
                {
                    "id": "33333333-3333-4333-8333-333333333333",
                    "name": "Inactive",
                    "slug": "inactive",
                    "description": None,
                    "is_active": False,
                    "created_at": "2026-05-17T10:00:00Z",
                    "updated_at": "2026-05-17T10:00:00Z",
                    "style_profile": None,
                    "quotes": [],
                    "phrase_templates": [],
                    "style_examples": [],
                },
            ],
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://backend.example",
    ) as http_client:
        client = BackendClient(base_url="https://backend.example", http_client=http_client)
        personas = await client.list_active_characters()

    assert [persona.name for persona in personas] == ["Roast Persona"]


@pytest.mark.asyncio
async def test_create_generation_posts_contract_payload() -> None:
    payload = GenerationCreate(
        person_name="Ada Lovelace",
        gender="female",
        birth_date="1990-01-02",
        birth_time="03:04:00",
        birth_place=GeoPoint(
            addr="Moscow, Russia",
            lat=55.7558,
            lng=37.6173,
            city="Moscow",
            nation="Russia",
            timezone="Europe/Moscow",
        ),
        persona_id="22222222-2222-4222-8222-222222222222",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/generations"
        assert request.headers["content-type"] == "application/json"
        assert request.read()
        return httpx.Response(
            201,
            json={
                "generation_id": "11111111-1111-4111-8111-111111111111",
                "status": "pending",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://backend.example",
    ) as http_client:
        client = BackendClient(base_url="https://backend.example", http_client=http_client)
        result = await client.create_generation(payload)

    assert result.generation_id == "11111111-1111-4111-8111-111111111111"
    assert result.status == "pending"


@pytest.mark.asyncio
async def test_backend_error_uses_fastapi_detail() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(404, json={"detail": "Active persona not found"})),
        base_url="https://backend.example",
    ) as http_client:
        client = BackendClient(base_url="https://backend.example", http_client=http_client)

        with pytest.raises(BackendAPIError, match="Active persona not found"):
            await client.create_generation(
                GenerationCreate(
                    person_name=None,
                    gender=None,
                    birth_date="1990-01-02",
                    birth_time="03:04:00",
                    birth_place=GeoPoint(
                        addr="Moscow, Russia",
                        lat=55.7558,
                        lng=37.6173,
                        city="Moscow",
                        nation="Russia",
                        timezone="Europe/Moscow",
                    ),
                    persona_id="22222222-2222-4222-8222-222222222222",
                )
            )
