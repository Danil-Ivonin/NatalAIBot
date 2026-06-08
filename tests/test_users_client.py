import httpx
import pytest

from natalaibot.http.users_client import UsersAPIError, UsersClient
from natalaibot.models import GeoPoint, PersonCreate


def _person_payload(person_id: str = "person-1") -> dict:
    return {
        "person_id": person_id,
        "person_name": "Ada",
        "gender": "female",
        "birth_date": "1990-01-02",
        "birth_time": "03:04:00",
        "birth_place": {
            "addr": "Moscow, Russia",
            "lat": 55.7558,
            "lng": 37.6173,
            "city": "Moscow",
            "nation": "Russia",
            "timezone": "Europe/Moscow",
        },
    }


@pytest.mark.asyncio
async def test_list_persons_calls_users_service_with_pagination() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/users/42/persons"
        assert request.url.params["limit"] == "5"
        assert request.url.params["offset"] == "10"
        return httpx.Response(200, json={"items": [_person_payload()], "total": 11})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://users.example") as http:
        client = UsersClient(base_url="https://users.example", http_client=http)
        page = await client.list_persons(telegram_id=42, limit=5, offset=10)

    assert page.total == 11
    assert page.items[0].person_id == "person-1"


@pytest.mark.asyncio
async def test_create_person_posts_birth_data() -> None:
    payload = PersonCreate(
        person_name="Ada",
        gender="female",
        birth_date="1990-01-02",
        birth_time="03:04:00",
        birth_place=GeoPoint(
            addr="Moscow",
            lat=55.75,
            lng=37.61,
            city="Moscow",
            nation="Russia",
            timezone="Europe/Moscow",
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/users/42/persons"
        assert request.headers["content-type"] == "application/json"
        body = request.read()
        assert b"person_name" in body
        return httpx.Response(201, json={"person_id": "person-1", **payload.model_dump(mode="json")})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://users.example") as http:
        client = UsersClient(base_url="https://users.example", http_client=http)
        result = await client.create_person(telegram_id=42, payload=payload)

    assert result.person_id == "person-1"


@pytest.mark.asyncio
async def test_get_and_delete_person_use_scoped_url() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json=_person_payload())
        return httpx.Response(204)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://users.example") as http:
        client = UsersClient(base_url="https://users.example", http_client=http)
        person = await client.get_person(telegram_id=42, person_id="person-1")
        await client.delete_person(telegram_id=42, person_id="person-1")

    assert person.person_id == "person-1"
    assert seen == [
        ("GET", "/api/users/42/persons/person-1"),
        ("DELETE", "/api/users/42/persons/person-1"),
    ]


@pytest.mark.asyncio
async def test_generation_links_are_created_and_listed() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.method == "POST":
            assert request.read() == b'{"generation_id":"generation-1"}'
            return httpx.Response(
                201,
                json={"generation_id": "generation-1", "created_at": "2026-06-08T10:00:00Z"},
            )
        return httpx.Response(
            200,
            json={
                "items": [{"generation_id": "generation-1", "created_at": "2026-06-08T10:00:00Z"}],
                "total": 1,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://users.example") as http:
        client = UsersClient(base_url="https://users.example", http_client=http)
        await client.create_generation_link(telegram_id=42, generation_id="generation-1")
        page = await client.list_generation_links(telegram_id=42, limit=5, offset=0)

    assert [item.generation_id for item in page.items] == ["generation-1"]
    assert seen == [
        ("POST", "/api/users/42/generations"),
        ("GET", "/api/users/42/generations"),
    ]


@pytest.mark.asyncio
async def test_users_error_uses_fastapi_detail() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(503, json={"detail": "Users unavailable"})),
        base_url="https://users.example",
    ) as http:
        client = UsersClient(base_url="https://users.example", http_client=http)

        with pytest.raises(UsersAPIError, match="Users unavailable"):
            await client.list_persons(telegram_id=42)
