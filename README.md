# NatalAIBot

Telegram bot for collecting birth data, selecting a backend persona, running paid natal chart generation, and rendering
the generated report.

## Configuration

Create `.env` or export variables:

```bash
BOT_TOKEN=telegram-bot-token
BACKEND_BASE_URL=http://localhost:8000
GENERATION_POLL_INTERVAL_SECONDS=3
GENERATION_POLL_ATTEMPTS=80
```

Payment is intentionally implemented as a stub in `natalaibot/payment.py`.

## Run

```bash
uv run python main.py
```

## Test

```bash
uv run pytest
```
