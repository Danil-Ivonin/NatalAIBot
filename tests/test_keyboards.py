from natalaibot.keyboards.generation import (
    character_keyboard,
    generation_history_keyboard,
    generation_menu_keyboard,
    new_generation_keyboard,
    person_selection_keyboard,
)
from natalaibot.keyboards.persons import person_detail_keyboard, persons_keyboard
from natalaibot.keyboards.start import main_keyboard
from natalaibot.models import Character, GenerationLinkRead, GeoPoint, PersonRead


def _person(idx: int) -> PersonRead:
    return PersonRead(
        person_id=f"person-{idx}",
        person_name=f"Person {idx}",
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
