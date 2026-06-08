from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup
import pytest

from natalaibot.handlers.generation import collect_confirm_data, run_generation
import natalaibot.handlers.generation as generation_module
from natalaibot.models import (
    Character,
    ChartImage,
    GenerationCreated,
    GenerationRead,
    GeoPoint,
    PersonRead,
    ReportSection,
    StyledNatalReport,
)


@pytest.mark.asyncio
async def test_run_generation_downloads_png_chart_and_sends_it_as_photo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = FakeMessage()
    callback = SimpleNamespace(message=message, answer=AsyncRecorder(), from_user=SimpleNamespace(id=42))
    state = FakeState()
    backend_client = FakeBackendClient(
        chart_image=ChartImage(url="https://storage.example/chart.png?signature=abc", mime_type="image/png")
    )
    settings = SimpleNamespace(generation_poll_attempts=1, generation_poll_interval_seconds=0)

    async def fake_download_url(url: str) -> bytes:
        assert url == "https://storage.example/chart.png?signature=abc"
        return b"\x89PNG\r\n\x1a\npng-bytes"

    users_client = FakeUsersClient()

    monkeypatch.setattr(generation_module, "_download_url", fake_download_url, raising=False)

    await run_generation(callback, state, backend_client, users_client, settings)

    assert message.calls[1] == ("answer_photo_file", b"\x89PNG\r\n\x1a\npng-bytes", "chart.png")
    assert [(call[0], call[1]) for call in message.calls[2:]] == [
        ("answer", "<b>Intro</b>\nIntro text."),
        ("answer", "<b>General</b>\nGeneral text."),
        ("answer", "<b>Love</b>\nLove text."),
        ("answer", "<b>Career</b>\nCareer text."),
        ("answer", "<b>Demons</b>\nDemons text."),
        ("answer", "<b>Final</b>\nFinal text."),
    ]
    assert state.cleared is True
    assert users_client.links == [(42, "generation-1")]


@pytest.mark.asyncio
async def test_run_generation_sends_report_sections_when_chart_image_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = FakeMessage()
    callback = SimpleNamespace(message=message, answer=AsyncRecorder(), from_user=SimpleNamespace(id=42))
    state = FakeState()
    backend_client = FakeBackendClient(chart_image=ChartImage(url="https://storage.example/chart.png", mime_type="image/png"))
    settings = SimpleNamespace(generation_poll_attempts=1, generation_poll_interval_seconds=0)

    async def fake_download_url(url: str) -> bytes:
        raise TelegramBadRequest(method=None, message="wrong HTTP URL specified")

    monkeypatch.setattr(generation_module, "_download_url", fake_download_url, raising=False)

    await run_generation(callback, state, backend_client, FakeUsersClient(), settings)

    assert [(call[0], call[1]) for call in message.calls[1:]] == [
        ("answer", "<b>Intro</b>\nIntro text."),
        ("answer", "<b>General</b>\nGeneral text."),
        ("answer", "<b>Love</b>\nLove text."),
        ("answer", "<b>Career</b>\nCareer text."),
        ("answer", "<b>Demons</b>\nDemons text."),
        ("answer", "<b>Final</b>\nFinal text."),
    ]
    assert state.cleared is True


@pytest.mark.asyncio
async def test_confirm_data_removes_reply_keyboard_and_sends_persona_inline_keyboard() -> None:
    message = FakeMessage(text="Верно")
    state = FakeState(
        {
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
    )
    users_client = FakeUsersClient()
    backend_client = FakeBackendClient()

    await collect_confirm_data(message, state, users_client, backend_client, telegram_id=42)

    assert state.state_name == "NatalForm:persona"
    assert isinstance(message.calls[0][2], InlineKeyboardMarkup)
    assert message.calls[0][1] == "Выберите персонажа, в чьём стиле будет выполнен разбор"


class FakeMessage:
    def __init__(self, text: str = "", photo_error: Exception | None = None) -> None:
        self.text = text
        self.calls = []
        self.photo_error = photo_error

    async def edit_text(self, text: str, **kwargs) -> None:
        self.calls.append(("edit_text", text))

    async def answer(self, text: str, **kwargs) -> None:
        self.calls.append(("answer", text, kwargs.get("reply_markup")))
        return FakeSentMessage()

    async def answer_photo(self, photo, **kwargs) -> None:
        if hasattr(photo, "data"):
            self.calls.append(("answer_photo_file", photo.data, photo.filename))
        else:
            self.calls.append(("answer_photo", photo))
        if self.photo_error:
            raise self.photo_error


class FakeState:
    def __init__(self, data: dict | None = None) -> None:
        self.cleared = False
        self.state_name = None
        self.data = data or {
            "selected_person": PersonRead(
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
            ).model_dump(mode="python"),
            "selected_character": Character(id="persona-1", name="Astrologer", slug="astrologer").model_dump(
                mode="python"
            ),
        }

    async def get_data(self) -> dict:
        return self.data

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def clear(self) -> None:
        self.cleared = True

    async def set_state(self, state) -> None:
        self.state_name = state.state


class FakeBackendClient:
    def __init__(self, chart_image: ChartImage | None = None) -> None:
        self.chart_image = chart_image or ChartImage(url="https://storage.example/chart.svg", mime_type="image/svg+xml")

    async def list_active_characters(self) -> list[Character]:
        return [
            Character(id="persona-1", name="Astrologer", slug="astrologer"),
            Character(id="persona-2", name="Oracle", slug="oracle"),
        ]

    async def create_generation(self, payload) -> GenerationCreated:
        return GenerationCreated(generation_id="generation-1", status="pending")

    async def get_generation(self, generation_id: str) -> GenerationRead:
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
            chart_image=self.chart_image,
        )


class FakeUsersClient:
    def __init__(self) -> None:
        self.links = []

    async def create_person(self, telegram_id, payload):
        return PersonRead(person_id="person-1", **payload.model_dump(mode="python"))

    async def create_generation_link(self, telegram_id, generation_id):
        self.links.append((telegram_id, generation_id))


class AsyncRecorder:
    def __init__(self) -> None:
        self.calls = []

    async def __call__(self, *args, **kwargs) -> None:
        self.calls.append((args, kwargs))


class FakeSentMessage:
    async def edit_reply_markup(self, **kwargs) -> None:
        raise AssertionError("reply keyboard removal should not be followed by edit_reply_markup")
