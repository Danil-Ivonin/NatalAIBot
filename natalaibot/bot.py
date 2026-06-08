from aiogram import Bot, Dispatcher

from natalaibot.config import Settings
from natalaibot.handlers.generation import router as generation_router
from natalaibot.handlers.persons import router as persons_router
from natalaibot.handlers.start import router as start_router
from natalaibot.http.backend_client import BackendClient
from natalaibot.http.users_client import UsersClient
from natalaibot.infra.payment import PaymentService


def create_dispatcher(
    settings: Settings,
    backend_client: BackendClient,
    users_client: UsersClient,
    payment_service: PaymentService,
) -> Dispatcher:
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


async def run_bot(settings: Settings) -> None:
    print("starting bot...")
    bot = Bot(token=settings.bot_token)
    backend_client = BackendClient(base_url=settings.backend_base_url)
    users_client = UsersClient(base_url=settings.users_base_url)
    dispatcher = create_dispatcher(
        settings=settings,
        backend_client=backend_client,
        users_client=users_client,
        payment_service=PaymentService(),
    )

    try:
        await dispatcher.start_polling(bot)
    finally:
        await backend_client.aclose()
        await users_client.aclose()
        await bot.session.close()
