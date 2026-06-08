from natalaibot.config import Settings
from natalaibot.models import (
    GenerationLinkCreate,
    GenerationLinksPage,
    GeoPoint,
    PersonCreate,
    PersonRead,
    PersonsPage,
)


def test_person_models_parse_users_service_payload() -> None:
    place = {
        "addr": "Moscow, Russia",
        "lat": 55.7558,
        "lng": 37.6173,
        "city": "Moscow",
        "nation": "Russia",
        "timezone": "Europe/Moscow",
    }

    create = PersonCreate(
        person_name="Ada",
        gender="female",
        birth_date="1990-01-02",
        birth_time="03:04:00",
        birth_place=GeoPoint.model_validate(place),
    )
    read = PersonRead.model_validate({"person_id": "person-1", **create.model_dump(mode="json")})
    page = PersonsPage.model_validate({"items": [read.model_dump(mode="json")], "total": 1})

    assert page.items[0].person_id == "person-1"
    assert page.items[0].birth_place.timezone == "Europe/Moscow"


def test_generation_link_models_parse_users_service_payload() -> None:
    payload = GenerationLinkCreate(generation_id="generation-1")
    page = GenerationLinksPage.model_validate(
        {"items": [{"generation_id": payload.generation_id, "created_at": "2026-06-08T10:00:00Z"}], "total": 1}
    )

    assert page.items[0].generation_id == "generation-1"
    assert page.total == 1


def test_settings_include_users_base_url_and_offer_url(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:token")
    monkeypatch.setenv("LOCATIONIQ_ACCESS_TOKEN", "location-token")
    monkeypatch.setenv("USERS_BASE_URL", "https://users.example")
    monkeypatch.setenv("OFFER_URL", "https://example.com/offer.pdf")

    settings = Settings()

    assert settings.users_base_url == "https://users.example"
    assert settings.offer_url == "https://example.com/offer.pdf"
