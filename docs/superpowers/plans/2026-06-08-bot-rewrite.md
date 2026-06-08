# NatalAIBot Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the menu-driven Telegram bot rewrite with separate users/persons and generation service clients.

**Architecture:** Keep aiogram 3. `natalaibot/bot.py` remains the composition root; handlers, keyboards, HTTP clients, formatting helpers, and models are split into focused files. The bot stores no durable data locally and records generation history through the users/persons service.

**Tech Stack:** Python 3.12, aiogram 3, httpx, pydantic 2, pytest, pytest-asyncio, ruff.

---

## File Structure

- `natalaibot/models.py`: add `PersonCreate`, `PersonRead`, `PersonsPage`, `GenerationLinkCreate`, `GenerationLinkRead`, `GenerationLinksPage`; keep existing generation and character models.
- `natalaibot/config.py`: add `USERS_BASE_URL` and `OFFER_URL`.
- `natalaibot/http/backend_client.py`: keep generation service contract; expose `list_active_characters`, `create_generation`, `get_generation`.
- `natalaibot/http/users_client.py`: implement users/persons service client and `UsersAPIError`.
- `natalaibot/keyboards/start.py`: build main menu with offer URL.
- `natalaibot/keyboards/persons.py`: build paginated person list and person detail keyboards.
- `natalaibot/keyboards/generation.py`: build generation menus, person selection, character selection, confirmation, history, and compatibility placeholder keyboards.
- `natalaibot/handlers/start.py`: `/start` and main menu callbacks.
- `natalaibot/handlers/persons.py`: persons list, pagination, detail, deletion.
- `natalaibot/handlers/generation.py`: generation menu, natal report flow, new-person FSM, payment stub flow, polling, history.
- `natalaibot/bot.py`: remove monolithic handlers, wire routers and clients.
- `tests/test_users_client.py`: users/persons service client tests.
- `tests/test_keyboards.py`: keyboard callback and pagination tests.
- `tests/test_handlers_start_persons.py`: start and persons handler tests.
- `tests/test_handlers_generation.py`: generation flow tests.
- Existing tests in `tests/test_backend_client.py`, `tests/test_bot_generation.py`, and `tests/test_formatting.py`: update imports and renamed API calls.

---

### Task 1: Models And Config

**Files:**
- Modify: `natalaibot/models.py`
- Modify: `natalaibot/config.py`
- Test: `tests/test_models_config.py`

- [ ] **Step 1: Write failing model/config tests**

Create `tests/test_models_config.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/test_models_config.py -v
```

Expected: FAIL because person/link models and settings fields do not exist.

- [ ] **Step 3: Implement models and settings**

In `natalaibot/models.py`, add these models without removing existing generation models:

```python
class PersonCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    person_name: str | None = None
    gender: Gender | None = None
    birth_date: str
    birth_time: str
    birth_place: GeoPoint


class PersonRead(PersonCreate):
    person_id: str


class PersonsPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[PersonRead]
    total: int = 0


class GenerationLinkCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    generation_id: str


class GenerationLinkRead(BaseModel):
    model_config = ConfigDict(extra="ignore")

    generation_id: str
    created_at: str | None = None


class GenerationLinksPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[GenerationLinkRead]
    total: int = 0
```

In `natalaibot/config.py`, add:

```python
users_base_url: str = Field(default="http://localhost:8001", alias="USERS_BASE_URL")
offer_url: str = Field(default="https://example.com/offer.pdf", alias="OFFER_URL")
```

- [ ] **Step 4: Run model/config tests**

Run:

```powershell
uv run pytest tests/test_models_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add natalaibot/models.py natalaibot/config.py tests/test_models_config.py
git commit -m "Add users service models and settings"
```

---

### Task 2: Users Service Client

**Files:**
- Modify: `natalaibot/http/users_client.py`
- Test: `tests/test_users_client.py`

- [ ] **Step 1: Write failing users client tests**

Create `tests/test_users_client.py`:

```python
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
        birth_place=GeoPoint(addr="Moscow", lat=55.75, lng=37.61, city="Moscow", nation="Russia", timezone="Europe/Moscow"),
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
            return httpx.Response(201, json={"generation_id": "generation-1", "created_at": "2026-06-08T10:00:00Z"})
        return httpx.Response(200, json={"items": [{"generation_id": "generation-1", "created_at": "2026-06-08T10:00:00Z"}], "total": 1})

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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/test_users_client.py -v
```

Expected: FAIL because `UsersClient` is empty.

- [ ] **Step 3: Implement `UsersClient`**

Write `natalaibot/http/users_client.py`:

```python
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
```

- [ ] **Step 4: Run users client tests**

Run:

```powershell
uv run pytest tests/test_users_client.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add natalaibot/http/users_client.py tests/test_users_client.py
git commit -m "Add users service client"
```

---

### Task 3: Keyboard Builders

**Files:**
- Modify: `natalaibot/keyboards/start.py`
- Modify: `natalaibot/keyboards/persons.py`
- Modify: `natalaibot/keyboards/generation.py`
- Test: `tests/test_keyboards.py`

- [ ] **Step 1: Write failing keyboard tests**

Create `tests/test_keyboards.py`:

```python
from natalaibot.keyboards.generation import (
    character_keyboard,
    generation_history_keyboard,
    generation_menu_keyboard,
    new_generation_keyboard,
    person_selection_keyboard,
)
from natalaibot.keyboards.persons import person_detail_keyboard, persons_keyboard
from natalaibot.keyboards.start import main_keyboard
from natalaibot.models import Character, GenerationLinkRead, PersonRead, GeoPoint


def _person(idx: int) -> PersonRead:
    return PersonRead(
        person_id=f"person-{idx}",
        person_name=f"Person {idx}",
        gender="female",
        birth_date="1990-01-02",
        birth_time="03:04:00",
        birth_place=GeoPoint(addr="Moscow", lat=55.75, lng=37.61, city="Moscow", nation="Russia", timezone="Europe/Moscow"),
    )


def _texts(markup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


def _callbacks(markup) -> list[str | None]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_main_keyboard_has_menu_and_offer_url() -> None:
    markup = main_keyboard("https://example.com/offer.pdf")

    assert _texts(markup) == ["Персоны", "Генерации", "Информация"]
    assert markup.inline_keyboard[2][0].url == "https://example.com/offer.pdf"


def test_persons_keyboard_limits_items_and_has_pagination() -> None:
    markup = persons_keyboard([_person(i) for i in range(7)], page=1, total=12, page_size=5)

    assert _texts(markup)[:5] == ["Person 0", "Person 1", "Person 2", "Person 3", "Person 4"]
    assert "persons:page:0" in _callbacks(markup)
    assert "persons:page:2" in _callbacks(markup)
    assert "main:menu" in _callbacks(markup)


def test_person_detail_keyboard_targets_person() -> None:
    markup = person_detail_keyboard(person_id="person-1", page=2)

    assert _callbacks(markup) == ["persons:delete:person-1:2", "persons:page:2"]


def test_generation_menus_have_expected_callbacks() -> None:
    assert _callbacks(generation_menu_keyboard()) == ["generation:new", "generation:list:0", "main:menu"]
    assert _callbacks(new_generation_keyboard()) == ["generation:natal", "generation:compatibility", "generation:menu"]


def test_person_selection_keyboard_adds_create_action() -> None:
    markup = person_selection_keyboard([_person(1)], page=0, total=1, page_size=5)

    assert _callbacks(markup) == ["generation:person:person-1:0", "generation:person:add", "generation:new"]


def test_character_keyboard_uses_character_callback_prefix() -> None:
    markup = character_keyboard([Character(id="char-1", name="Oracle", slug="oracle")])

    assert _texts(markup) == ["Oracle"]
    assert _callbacks(markup) == ["generation:character:char-1"]


def test_generation_history_keyboard_has_status_callbacks() -> None:
    markup = generation_history_keyboard(
        [GenerationLinkRead(generation_id="generation-1", created_at="2026-06-08T10:00:00Z")],
        page=0,
        total=1,
        page_size=5,
    )

    assert _callbacks(markup) == ["generation:history:open:generation-1:0", "generation:menu"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/test_keyboards.py -v
```

Expected: FAIL because builders are missing or have old callbacks.

- [ ] **Step 3: Implement keyboard builders**

Implement callback strings exactly as asserted in tests. Use `InlineKeyboardBuilder`, call `builder.adjust(1)` for list buttons, and manually add pagination rows so previous/next stay on one row.

Core function signatures:

```python
def main_keyboard(offer_url: str) -> InlineKeyboardMarkup: ...
def persons_keyboard(persons: list[PersonRead], page: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup: ...
def person_detail_keyboard(person_id: str, page: int) -> InlineKeyboardMarkup: ...
def generation_menu_keyboard() -> InlineKeyboardMarkup: ...
def new_generation_keyboard() -> InlineKeyboardMarkup: ...
def person_selection_keyboard(persons: list[PersonRead], page: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup: ...
def character_keyboard(characters: list[Character]) -> InlineKeyboardMarkup: ...
def generation_history_keyboard(links: list[GenerationLinkRead], page: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup: ...
def back_to_generation_menu_keyboard() -> InlineKeyboardMarkup: ...
def generation_confirm_keyboard() -> InlineKeyboardMarkup: ...
```

Use these exact callback prefixes:

```python
"main:menu"
"main:persons"
"main:generation"
"persons:page:{page}"
"persons:open:{person_id}:{page}"
"persons:delete:{person_id}:{page}"
"generation:menu"
"generation:new"
"generation:natal"
"generation:compatibility"
"generation:person:{person_id}:{page}"
"generation:person:add"
"generation:person_page:{page}"
"generation:character:{character_id}"
"generation:confirm:pay"
"generation:confirm:back"
"generation:list:{page}"
"generation:history:open:{generation_id}:{page}"
```

- [ ] **Step 4: Run keyboard tests**

Run:

```powershell
uv run pytest tests/test_keyboards.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add natalaibot/keyboards/start.py natalaibot/keyboards/persons.py natalaibot/keyboards/generation.py tests/test_keyboards.py
git commit -m "Add bot menu keyboards"
```

---

### Task 4: Start And Persons Handlers

**Files:**
- Modify: `natalaibot/handlers/start.py`
- Modify: `natalaibot/handlers/persons.py`
- Test: `tests/test_handlers_start_persons.py`

- [ ] **Step 1: Write failing handler tests**

Create `tests/test_handlers_start_persons.py` with fake messages/callbacks:

```python
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
        birth_place=GeoPoint(addr="Moscow", lat=55.75, lng=37.61, city="Moscow", nation="Russia", timezone="Europe/Moscow"),
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/test_handlers_start_persons.py -v
```

Expected: FAIL because handlers are missing current signatures/behavior.

- [ ] **Step 3: Implement start/persons handlers**

Implement:

```python
PAGE_SIZE = 5

@router.message(CommandStart())
async def start(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    await message.answer("Выберите раздел:", reply_markup=main_keyboard(settings.offer_url))
```

In persons handlers:

```python
def _page_from_callback(data: str, prefix: str) -> int:
    return max(int(data.removeprefix(prefix)), 0)

def format_person(person: PersonRead) -> str:
    gender = {"female": "женский", "male": "мужской", None: "не указан"}[person.gender]
    return (
        f"Имя: {person.person_name or 'не указано'}\n"
        f"Пол: {gender}\n"
        f"Дата рождения: {person.birth_date} {person.birth_time}\n"
        f"Место рождения: {person.birth_place.addr}"
    )
```

Handle `UsersAPIError` by editing text to:

```python
"Сервис персон временно недоступен. Попробуйте позже."
```

with a back button to main menu.

- [ ] **Step 4: Run start/persons tests**

Run:

```powershell
uv run pytest tests/test_handlers_start_persons.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add natalaibot/handlers/start.py natalaibot/handlers/persons.py tests/test_handlers_start_persons.py
git commit -m "Add start and persons handlers"
```

---

### Task 5: Generation Handlers And Bot Wiring

**Files:**
- Modify: `natalaibot/handlers/generation.py`
- Modify: `natalaibot/bot.py`
- Modify: `main.py` only if imports need adjustment
- Test: `tests/test_handlers_generation.py`

- [ ] **Step 1: Write focused generation handler tests**

Create `tests/test_handlers_generation.py`:

```python
from types import SimpleNamespace

import pytest

from natalaibot.handlers.generation import (
    NatalForm,
    collect_confirm_data,
    run_generation,
    show_compatibility_placeholder,
)
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


class FakePaymentService:
    async def request_payment(self, telegram_user_id):
        return SimpleNamespace(is_paid=True, payment_id=f"stub-{telegram_user_id}")


def _person() -> PersonRead:
    return PersonRead(
        person_id="person-1",
        person_name="Ada",
        gender="female",
        birth_date="1990-01-02",
        birth_time="03:04:00",
        birth_place=GeoPoint(addr="Moscow", lat=55.75, lng=37.61, city="Moscow", nation="Russia", timezone="Europe/Moscow"),
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
        "birth_place": GeoPoint(addr="Moscow", lat=55.75, lng=37.61, city="Moscow", nation="Russia", timezone="Europe/Moscow"),
    }

    await collect_confirm_data(message, state, users_client=FakeUsersClient(), backend_client=FakeBackendClient(), telegram_id=42)

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
```

- [ ] **Step 2: Run generation handler tests to verify failure**

Run:

```powershell
uv run pytest tests/test_handlers_generation.py -v
```

Expected: FAIL because new generation module is empty or not wired.

- [ ] **Step 3: Move monolithic generation helpers into `handlers/generation.py`**

Move or recreate these helpers from current `natalaibot/bot.py`:

```python
_wait_for_generation
_send_chart_image
_download_url
_filename_from_url
_parse_gender
_parse_confirm
_parse_date
_parse_time
```

Keep behavior compatible with existing tests: SVG/chart image delivery remains best-effort and report sections use `format_report_sections` and `split_telegram_message`.

- [ ] **Step 4: Implement generation router flow**

Implement `NatalForm` in `natalaibot/handlers/generation.py` with states:

```python
class NatalForm(StatesGroup):
    person_name = State()
    gender = State()
    birth_date = State()
    birth_time = State()
    birth_place = State()
    confirm_data = State()
    persona = State()
    payment = State()
```

Implement callbacks:

```python
generation:menu
generation:new
generation:natal
generation:compatibility
generation:person_page:{page}
generation:person:{person_id}:{page}
generation:person:add
generation:character:{character_id}
generation:confirm:pay
generation:confirm:back
generation:list:{page}
generation:history:open:{generation_id}:{page}
```

For new person creation, collect birth data as in current `bot.py`, geocode through `geocode_address`, and on confirmation:

```python
payload = PersonCreate(
    person_name=data.get("person_name"),
    gender=data.get("gender"),
    birth_date=data["birth_date"],
    birth_time=data["birth_time"],
    birth_place=data["birth_place"],
)
person = await users_client.create_person(telegram_id=telegram_id, payload=payload)
await state.update_data(selected_person=person.model_dump(mode="python"))
```

For selected existing person:

```python
person = await users_client.get_person(telegram_id=callback.from_user.id, person_id=person_id)
await state.update_data(selected_person=person.model_dump(mode="python"))
```

For final generation:

```python
person = PersonRead.model_validate(data["selected_person"])
character = Character.model_validate(data["selected_character"])
payload = GenerationCreate(
    person_name=person.person_name,
    gender=person.gender,
    birth_date=person.birth_date,
    birth_time=person.birth_time,
    birth_place=person.birth_place,
    persona_id=character.id,
)
created = await backend_client.create_generation(payload)
try:
    await users_client.create_generation_link(callback.from_user.id, created.generation_id)
except Exception:
    await callback.message.answer("Генерация запущена, но может не появиться в истории.")
```

- [ ] **Step 5: Wire bot composition root**

In `natalaibot/bot.py`, import routers and clients:

```python
from natalaibot.handlers.generation import router as generation_router
from natalaibot.handlers.persons import router as persons_router
from natalaibot.handlers.start import router as start_router
from natalaibot.http.backend_client import BackendClient
from natalaibot.http.users_client import UsersClient
from natalaibot.infra.payment import PaymentService
```

Implement:

```python
def create_dispatcher(settings: Settings, backend_client: BackendClient, users_client: UsersClient, payment_service: PaymentService) -> Dispatcher:
    dispatcher = Dispatcher(
        settings=settings,
        backend_client=backend_client,
        users_client=users_client,
        payment_service=payment_service,
    )
    dispatcher.include_router(start_router)
    dispatcher.include_router(persons_router)
    dispatcher.include_router(generation_router)
    return dispatcher
```

In `run_bot`, create and close both clients:

```python
backend_client = BackendClient(base_url=settings.backend_base_url)
users_client = UsersClient(base_url=settings.users_base_url)
...
finally:
    await backend_client.aclose()
    await users_client.aclose()
    await bot.session.close()
```

- [ ] **Step 6: Run generation tests**

Run:

```powershell
uv run pytest tests/test_handlers_generation.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add natalaibot/handlers/generation.py natalaibot/bot.py tests/test_handlers_generation.py
git commit -m "Add generation flow handlers"
```

---

### Task 6: Update Existing Tests And Imports

**Files:**
- Modify: `tests/test_backend_client.py`
- Modify: `tests/test_bot_generation.py`
- Modify: `tests/test_formatting.py`
- Modify: any stale imports under `natalaibot/`

- [ ] **Step 1: Run full tests to find stale imports**

Run:

```powershell
uv run pytest -v
```

Expected: FAIL on stale imports such as `natalaibot.backend_client`, `natalaibot.formatting`, and old `Persona` naming.

- [ ] **Step 2: Update test imports and fake clients**

Make these import changes:

```python
from natalaibot.http import backend_client
from natalaibot.http.backend_client import BackendAPIError, BackendClient
from natalaibot.infra.formatting import format_report_sections
from natalaibot.models import Character
```

Replace fake methods named `list_active_personas` with:

```python
async def list_active_characters(self) -> list[Character]:
    return [
        Character(id="persona-1", name="Astrologer", slug="astrologer"),
        Character(id="persona-2", name="Oracle", slug="oracle"),
    ]
```

Update imports of `run_generation` and `collect_confirm_data` to:

```python
from natalaibot.handlers.generation import collect_confirm_data, run_generation
import natalaibot.handlers.generation as generation_module
```

- [ ] **Step 3: Run full tests**

Run:

```powershell
uv run pytest -v
```

Expected: PASS or only failures caused by tests that still assert old monolithic text.

- [ ] **Step 4: Update old text assertions**

Replace old `/start` text expectations with:

```python
"Выберите раздел:"
```

Replace old character prompt expectations with:

```python
"Выберите персонажа, в чьём стиле будет выполнен разбор"
```

- [ ] **Step 5: Run full tests again**

Run:

```powershell
uv run pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add tests natalaibot
git commit -m "Update tests for modular bot rewrite"
```

---

### Task 7: Lint And Final Verification

**Files:**
- Modify only files needed to satisfy lint or test failures.

- [ ] **Step 1: Run formatter/linter**

Run:

```powershell
uv run ruff check .
```

Expected: PASS or actionable lint errors.

- [ ] **Step 2: Fix lint errors**

For unused imports, remove the import. For line length, split function calls over multiple lines using the existing style. Do not rewrite unrelated code.

- [ ] **Step 3: Run full verification**

Run:

```powershell
uv run pytest -v
uv run ruff check .
```

Expected: both commands PASS.

- [ ] **Step 4: Commit final cleanup**

If Step 2 changed files:

```powershell
git add natalaibot tests
git commit -m "Clean up bot rewrite lint issues"
```

If Step 2 changed nothing, do not create an empty commit.

---

## Self-Review

Spec coverage:

- Main menu and offer URL: Task 3 and Task 4.
- Persons list, pagination, detail, delete: Task 2, Task 3, Task 4.
- Separate users/persons service URL and generation service URL: Task 1, Task 2, Task 5.
- Generation menus and compatibility placeholder: Task 3, Task 5.
- New-person FSM and immediate users-service save: Task 5.
- Existing-person selection and character selection: Task 5.
- Payment stub and unchanged generation payload: Task 5.
- Generation-link history stored in users/persons service: Task 2 and Task 5.
- Generation history detail loading from generation service: Task 5.
- Error handling and best-effort chart image: Task 5 and Task 6.
- Regression tests and lint: Task 6 and Task 7.

Placeholder scan: the plan defines concrete file paths, callbacks, commands, and model/client signatures.

Type consistency: model names are `PersonCreate`, `PersonRead`, `PersonsPage`, `GenerationLinkCreate`, `GenerationLinkRead`, `GenerationLinksPage`, and `Character`; these names are used consistently across client, keyboard, and handler tasks.
