from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardRemove
import pytest

from natalaibot.bot import collect_confirm_data, run_generation
import natalaibot.bot as bot_module
from natalaibot.models import (
    ChartImage,
    GenerationCreated,
    GenerationRead,
    GeoPoint,
    Persona,
    ReportSection,
    StyledNatalReport,
)


@pytest.mark.asyncio
async def test_run_generation_sends_svg_chart_as_document_before_report_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    message = FakeMessage()
    callback = SimpleNamespace(message=message, answer=AsyncRecorder())
    state = FakeState()
    backend_client = FakeBackendClient()
    settings = SimpleNamespace(generation_poll_attempts=1, generation_poll_interval_seconds=0)

    async def fake_download_url(url: str) -> bytes:
        assert url == "https://storage.example/chart.svg"
        return b"<svg />"

    monkeypatch.setattr(bot_module, "_download_url", fake_download_url, raising=False)

    await run_generation(callback, state, backend_client, settings)

    assert message.calls[1] == ("answer_document", b"<svg />", "chart.svg")
    assert [(call[0], call[1]) for call in message.calls[2:]] == [
        ("answer", "<b>Intro</b>\nIntro text."),
        ("answer", "<b>General</b>\nGeneral text."),
        ("answer", "<b>Love</b>\nLove text."),
        ("answer", "<b>Career</b>\nCareer text."),
        ("answer", "<b>Demons</b>\nDemons text."),
        ("answer", "<b>Final</b>\nFinal text."),
    ]
    assert state.cleared is True


@pytest.mark.asyncio
async def test_run_generation_sends_raster_chart_as_photo_before_report_sections() -> None:
    message = FakeMessage()
    callback = SimpleNamespace(message=message, answer=AsyncRecorder())
    state = FakeState()
    backend_client = FakeBackendClient(chart_image=ChartImage(url="https://storage.example/chart.png", mime_type="image/png"))
    settings = SimpleNamespace(generation_poll_attempts=1, generation_poll_interval_seconds=0)

    await run_generation(callback, state, backend_client, settings)

    assert message.calls[1] == ("answer_photo", "https://storage.example/chart.png")
    assert [(call[0], call[1]) for call in message.calls[2:]] == [
        ("answer", "<b>Intro</b>\nIntro text."),
        ("answer", "<b>General</b>\nGeneral text."),
        ("answer", "<b>Love</b>\nLove text."),
        ("answer", "<b>Career</b>\nCareer text."),
        ("answer", "<b>Demons</b>\nDemons text."),
        ("answer", "<b>Final</b>\nFinal text."),
    ]
    assert state.cleared is True


@pytest.mark.asyncio
async def test_run_generation_sends_report_sections_when_chart_image_fails() -> None:
    message = FakeMessage(photo_error=TelegramBadRequest(method=None, message="wrong HTTP URL specified"))
    callback = SimpleNamespace(message=message, answer=AsyncRecorder())
    state = FakeState()
    backend_client = FakeBackendClient(chart_image=ChartImage(url="https://storage.example/chart.png", mime_type="image/png"))
    settings = SimpleNamespace(generation_poll_attempts=1, generation_poll_interval_seconds=0)

    await run_generation(callback, state, backend_client, settings)

    assert message.calls[1] == ("answer_photo", "https://storage.example/chart.png")
    assert [(call[0], call[1]) for call in message.calls[2:]] == [
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
    state = FakeState()
    backend_client = FakeBackendClient()

    await collect_confirm_data(message, state, backend_client)

    assert state.state_name == "NatalForm:persona"
    assert isinstance(message.calls[0][2], ReplyKeyboardRemove)
    assert isinstance(message.calls[1][2], InlineKeyboardMarkup)
    assert message.calls[1][1] == "Выбери персонажа, от чьего имени будет разобрана натальная карта:"


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

    async def answer_photo(self, photo: str, **kwargs) -> None:
        self.calls.append(("answer_photo", photo))
        if self.photo_error:
            raise self.photo_error

    async def answer_document(self, document, **kwargs) -> None:
        self.calls.append(("answer_document", document.data, document.filename))
        if self.photo_error:
            raise self.photo_error


class FakeState:
    def __init__(self) -> None:
        self.cleared = False
        self.state_name = None

    async def get_data(self) -> dict:
        return {
            "person_name": "Ada",
            "gender": "female",
            "birth_date": "1990-01-02",
            "birth_time": "03:04:00",
            "birth_place": GeoPoint(addr="Moscow", lat=55.75, lng=37.61, timezone="Europe/Moscow"),
            "persona_id": "persona-1",
        }

    async def clear(self) -> None:
        self.cleared = True

    async def set_state(self, state) -> None:
        self.state_name = state.state


class FakeBackendClient:
    def __init__(self, chart_image: ChartImage | None = None) -> None:
        self.chart_image = chart_image or ChartImage(url="https://storage.example/chart.svg", mime_type="image/svg+xml")

    async def list_active_personas(self) -> list[Persona]:
        return [
            Persona(id="persona-1", name="Astrologer", slug="astrologer"),
            Persona(id="persona-2", name="Oracle", slug="oracle"),
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


class AsyncRecorder:
    def __init__(self) -> None:
        self.calls = []

    async def __call__(self, *args, **kwargs) -> None:
        self.calls.append((args, kwargs))


class FakeSentMessage:
    async def edit_reply_markup(self, **kwargs) -> None:
        raise AssertionError("reply keyboard removal should not be followed by edit_reply_markup")
