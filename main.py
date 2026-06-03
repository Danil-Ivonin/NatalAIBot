import asyncio

from pydantic import ValidationError

from natalaibot.bot import run_bot
from natalaibot.config import Settings


def main() -> None:
    try:
        settings = Settings()
    except ValidationError as exc:
        raise SystemExit(f"Configuration error:\n{exc}") from exc

    asyncio.run(run_bot(settings))


if __name__ == "__main__":
    main()
