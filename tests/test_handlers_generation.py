from types import SimpleNamespace

import pytest

from natalaibot.handlers.generation import collect_confirm_data, run_generation, show_compatibility_placeholder
from natalaibot.models import (
    Character,
    GenerationCreated,
    GenerationRead,
    GeoPoint,
    PersonRead,
    ReportSection,
    StyledNatalReport,
)


class FakeMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.calls = []

    async def answer(self, text: str, **kwargs):
        self.calls.append(("answer", text, kwargs.get("reply_markup")))

    async def edit_text(self, text: str, **kwargs):
        self.calls.append(("edit_text", text, kwargs.get("reply_markup")))

    async def answer_photo(self, photo, **kwargs):
        self.calls.append(("answer_photo", getattr(photo, "filename", None)))


class FakeCallback:
    def __init__(self, data: str = "generation:confirm:pay") -> None:
        self.data = data
        self.from_user = SimpleNamespace(id=42)
        self.message = FakeMessage()
        self.answered = False

    async def answer(self, *args, **kwargs):
        self.answered = True


class FakeState:
    def __init__(self) -> None:
        self.data = {
            "selected_person": _person().model_dump(mode="python"),
            "selected_character": Character(id="char-1", name="Oracle", slug="oracle").model_dump(mode="python"),
        }
        self.state_name = None
        self.cleared = False

    async def get_data(self):
        return self.data

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def set_state(self, state):
        self.state_name = state.state

    async def clear(self):
        self.cleared = True


class FakeUsersClient:
    def __init__(self, fail_link: bool = False) -> None:
        self.fail_link = fail_link
        self.created_persons = []
        self.links = []

    async def create_person(self, telegram_id, payload):
        self.created_persons.append((telegram_id, payload))
        return PersonRead(person_id="person-1", **payload.model_dump(mode="python"))

    async def create_generation_link(self, telegram_id, generation_id):
        if self.fail_link:
            raise RuntimeError("users down")
        self.links.append((telegram_id, generation_id))


class FakeBackendClient:
    async def list_active_characters(self):
        return [Character(id="char-1", name="Oracle", slug="oracle")]

    async def create_generation(self, payload):
        self.payload = payload
        return GenerationCreated(generation_id="generation-1", status="pending")

    async def get_generation(self, generation_id):
        return GenerationRead(
            generation_id=generation_id,
            status="completed",
            result_text=StyledNatalReport(
                title="Natal report",
                intro=ReportSection(title="Intro", text="Intro text."),
                general=ReportSection(title="General", text="General text."),
                love_and_sex=ReportSection(title="Love", text="Love text."),
                career_and_money=ReportSection(title="Career", text="Career text."),
                demons=ReportSection(title="Demons", text="Demons text."),
                final_summary=ReportSection(title="Final", text="Final text."),
            ),
            chart_image=None,
        )


def _person() -> PersonRead:
    return PersonRead(
        person_id="person-1",
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
async def test_compatibility_placeholder_is_stub() -> None:
    callback = FakeCallback("generation:compatibility")

    await show_compatibility_placeholder(callback)

    assert callback.message.calls[0][1] == "Раздел проверки совместимости скоро появится."


@pytest.mark.asyncio
async def test_confirm_data_saves_person_and_loads_characters() -> None:
    message = FakeMessage("Верно")
    state = FakeState()
    state.data = {
        "person_name": "Ada",
        "gender": "female",
        "birth_date": "1990-01-02",
        "birth_time": "03:04:00",
        "birth_place": GeoPoint(
            addr="Moscow",
            lat=55.75,
            lng=37.61,
            city="Moscow",
            nation="Russia",
            timezone="Europe/Moscow",
        ),
    }

    await collect_confirm_data(
        message,
        state,
        users_client=FakeUsersClient(),
        backend_client=FakeBackendClient(),
        telegram_id=42,
    )

    assert state.state_name == "NatalForm:persona"
    assert "Выберите персонажа" in message.calls[-1][1]


@pytest.mark.asyncio
async def test_run_generation_creates_backend_generation_and_history_link() -> None:
    callback = FakeCallback()
    state = FakeState()
    users = FakeUsersClient()
    backend = FakeBackendClient()
    settings = SimpleNamespace(generation_poll_attempts=1, generation_poll_interval_seconds=0)

    await run_generation(callback, state, backend_client=backend, users_client=users, settings=settings)

    assert backend.payload.person_name == "Ada"
    assert users.links == [(42, "generation-1")]
    assert state.cleared is True
