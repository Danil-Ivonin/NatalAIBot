from types import SimpleNamespace

import pytest

from natalaibot.handlers.persons import delete_person, open_person, show_persons
from natalaibot.handlers.start import start
from natalaibot.models import GeoPoint, PersonRead, PersonsPage


class FakeMessage:
    def __init__(self) -> None:
        self.calls = []

    async def answer(self, text: str, **kwargs):
        self.calls.append(("answer", text, kwargs.get("reply_markup")))

    async def edit_text(self, text: str, **kwargs):
        self.calls.append(("edit_text", text, kwargs.get("reply_markup")))


class FakeCallback:
    def __init__(self, data: str = "main:persons") -> None:
        self.data = data
        self.from_user = SimpleNamespace(id=42)
        self.message = FakeMessage()
        self.answered = False

    async def answer(self, *args, **kwargs) -> None:
        self.answered = True


class FakeState:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


class FakeUsersClient:
    def __init__(self) -> None:
        self.deleted = []

    async def list_persons(self, telegram_id: int, limit: int = 5, offset: int = 0):
        return PersonsPage(items=[_person("person-1")], total=1)

    async def get_person(self, telegram_id: int, person_id: str):
        return _person(person_id)

    async def delete_person(self, telegram_id: int, person_id: str):
        self.deleted.append((telegram_id, person_id))


def _person(person_id: str) -> PersonRead:
    return PersonRead(
        person_id=person_id,
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


@pytest.mark.asyncio
async def test_start_clears_state_and_shows_main_keyboard() -> None:
    message = FakeMessage()
    state = FakeState()
    settings = SimpleNamespace(offer_url="https://example.com/offer.pdf")

    await start(message, state, settings)

    assert state.cleared is True
    assert message.calls[0][1] == "Выберите раздел:"
    assert message.calls[0][2].inline_keyboard[2][0].url == "https://example.com/offer.pdf"


@pytest.mark.asyncio
async def test_show_persons_lists_users_persons() -> None:
    callback = FakeCallback("main:persons")

    await show_persons(callback, users_client=FakeUsersClient())

    assert callback.message.calls[0][0] == "edit_text"
    assert callback.message.calls[0][1] == "Ваши персоны:"
    assert callback.answered is True


@pytest.mark.asyncio
async def test_open_person_shows_person_detail() -> None:
    callback = FakeCallback("persons:open:person-1:0")

    await open_person(callback, users_client=FakeUsersClient())

    assert "Ada" in callback.message.calls[0][1]
    assert "1990-01-02" in callback.message.calls[0][1]


@pytest.mark.asyncio
async def test_delete_person_deletes_and_returns_to_list() -> None:
    callback = FakeCallback("persons:delete:person-1:0")
    users = FakeUsersClient()

    await delete_person(callback, users_client=users)

    assert users.deleted == [(42, "person-1")]
    assert callback.message.calls[0][1] == "Персона удалена."
