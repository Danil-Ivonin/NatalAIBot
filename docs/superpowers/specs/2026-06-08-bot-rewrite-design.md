# NatalAIBot Rewrite Design

Date: 2026-06-08

## Goal

Rewrite the Telegram bot navigation and generation flow while keeping aiogram 3 and the current generation backend contract. The bot should become a thin client over two separate backend services:

- the users/persons service stores people and the user's generation history links;
- the generation service stores characters, starts natal report generation, and returns generation results.

The rewrite should replace the current start-to-generation monolith with menu-driven handlers, paginated lists, explicit service clients, and focused tests.

## Architecture

`natalaibot/bot.py` remains the composition root. It creates the `Dispatcher`, `BackendClient`, `UsersClient`, `PaymentService`, injects them into aiogram DI, and includes routers.

Handlers are split by user-facing area:

- `natalaibot/handlers/start.py`: `/start`, main menu, information offer link.
- `natalaibot/handlers/persons.py`: persons menu, pagination, person detail, person deletion.
- `natalaibot/handlers/generation.py`: generation menu, natal report flow, generation history, compatibility placeholder.

Keyboard builders stay in `natalaibot/keyboards/*.py` and contain no business logic. HTTP code stays behind service clients:

- `natalaibot/http/backend_client.py`: existing generation service and characters API.
- `natalaibot/http/users_client.py`: persons API and user generation-link API.

`natalaibot/models.py` owns Pydantic models for person data, paginated responses, generation history links, characters, and generation payload/result models.

## Service Contracts

The users/persons service does not use API versioning.

Persons:

- `GET /api/users/{telegram_id}/persons?limit=5&offset=0`
- `POST /api/users/{telegram_id}/persons`
- `GET /api/users/{telegram_id}/persons/{person_id}`
- `DELETE /api/users/{telegram_id}/persons/{person_id}`

The user can have many persons. Every person operation is scoped by `telegram_id`; destructive actions should not be possible across users.

Generation links stored in the users/persons service:

- `POST /api/users/{telegram_id}/generations` with `{"generation_id": "..."}`
- `GET /api/users/{telegram_id}/generations?limit=5&offset=0`

The generation link list response should include `items` and `total`. Each item includes at least `generation_id` and `created_at`, sorted newest first by the users/persons service.

The generation service keeps its current versioned contract:

- `GET /api/v1/personas` for active characters.
- `POST /api/v1/generations` for starting generation.
- `GET /api/v1/generations/{generation_id}` for status/result polling and history details.

The generation payload is not changed. The bot sends full person birth data and selected `persona_id`; the generation service does not call the users/persons service.

## Main Menu

`/start` clears FSM state and shows inline buttons:

- `Персоны`
- `Генерации`
- `Информация`

`Информация` is a URL button pointing to the offer file link from configuration, for example `OFFER_URL`.

## Persons Flow

The persons menu loads up to five persons for the current Telegram user from the users/persons service. It shows:

- zero to five person buttons;
- previous and next pagination buttons when applicable;
- `назад`.

Selecting a person opens a detail screen with a concise formatted summary and buttons:

- `удалить персону`;
- `назад`.

Deleting a person calls the users/persons service `DELETE` endpoint and returns to the current persons list page.

## Generations Menu

The generation menu shows:

- `Запустить новую генерацию`;
- `Список генераций`;
- `назад`.

`Запустить новую генерацию` shows:

- `Сделать разбор натальной карты`;
- `Проверить совместимость`;
- `назад`.

`Проверить совместимость` is currently a placeholder. It immediately shows a message that compatibility checking will appear later and offers a back button.

## Natal Report Flow

`Сделать разбор натальной карты` first asks the user to choose a person:

- zero to five existing persons;
- previous and next pagination buttons when applicable;
- `добавить нового человека`;
- `назад`.

If the user adds a new person, the bot starts the existing birth-data FSM:

- `person_name`
- `gender`
- `birth_date`
- `birth_time`
- `birth_place`
- `confirm_data`

After `confirm_data`, the bot saves the person to the users/persons service immediately. The returned `person_id` becomes the selected person for the rest of the flow. If saving fails, the bot does not start generation.

For an existing or newly-created person, the bot loads active characters from the generation service and asks:

`Выберите персонажа, в чьём стиле будет выполнен разбор`

After character selection, the bot shows a final confirmation containing the selected person's birth data and selected character information. The buttons are:

- `оплатить`;
- `назад`.

Payment remains a local stub through the current `PaymentService`.

After payment succeeds, the bot starts generation through the existing generation payload:

- `person_name`
- `gender`
- `birth_date`
- `birth_time`
- `birth_place`
- `persona_id`

When `create_generation` returns `generation_id`, the bot records that id in the users/persons service through `POST /api/users/{telegram_id}/generations`. The bot then polls the generation service for completion and sends the result to the user.

The bot sends the chart image first when available. Image delivery is best-effort: if download or Telegram upload fails, the bot still sends the report text sections.

## Generation History

`Список генераций` loads generation links from the users/persons service, five per page, newest first. For each `generation_id`, the bot calls the generation service `GET /api/v1/generations/{generation_id}` to load current status and available details.

The history page shows zero to five generations with pagination and a back button. Completed generations can be selected and resent to the user. Pending or processing generations show status. Failed generations show failure status and the generation error message when available.

If a generation was created successfully but saving the generation link to the users/persons service failed, the bot continues polling and sends the result. It also tells the user that the generation may not appear in history.

## Error Handling

For users/persons service failures while listing persons or generations, the bot shows a short temporary-unavailable message and a back button.

If the users/persons service cannot save a new person, the bot stops before payment and generation.

If the generation service cannot return characters, the bot returns the user to the previous generation action screen.

If generation creation fails, the bot shows the backend error and does not write a generation link.

If polling finishes without a completed result, the bot tells the user that generation is still running and suggests checking the generation list later.

## Testing

Add or update tests for:

- `UsersClient` persons pagination, create person, delete person, create generation link, list generation links;
- keyboard builders, including item limits and pagination buttons;
- `/start` main menu and information URL button;
- existing-person natal generation flow;
- new-person creation flow and immediate save to users/persons service;
- successful generation start followed by generation-link save;
- generation-link save failure fallback;
- generation history rendering and completed-result resend;
- compatibility placeholder.

Existing tests should be updated for renamed models and imports, including `Character` instead of any older `Persona` naming where needed.

## Out Of Scope

The rewrite does not implement real payments.

The rewrite does not implement compatibility checking.

The rewrite does not add local persistent storage in the bot.

The rewrite does not make the generation service call the users/persons service.
