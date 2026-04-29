import asyncio
import sys
from loguru import logger # Импортируем Loguru
from src.bot import bot, dp
from src.database.core import init_db
from src.handlers import user_start, user_buy, user_profile, user_language, admin_tools, admin_stats, user_promo, user_help, user_referral, user_billing, user_qrcode, user_payment, user_signin
from src.middlewares.i18n import I18nMiddleware
from src.middlewares.clear_state import ClearStateMiddleware
from src.scheduler import start_scheduler
from src.promo_scheduler import setup_promo_scheduler, promo_router

async def main():
    # 1. Настройка логгера
    logger.remove() # Удаляем стандартный обработчик
    
    # Добавляем красивый вывод в консоль
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Добавляем запись в файл (чтобы не потерять историю)
    logger.add("bot.log", rotation="10 MB", level="DEBUG")

    logger.info("🚀 Запускаем бота...")

    # 2. Инициализация БД
    try:
        await init_db()
        logger.success("✅ База данных подключена!")
    except Exception as e:
        logger.error(f"❌ Ошибка БД: {e}")
        return

    # Подключаем Middleware
    dp.message.middleware(I18nMiddleware())
    dp.message.middleware(ClearStateMiddleware())
    dp.callback_query.middleware(I18nMiddleware())

    # 3. Регистрация роутеров
    dp.include_routers(
        user_start.router,
        user_buy.router,
        user_profile.router,
        user_language.router,
        admin_tools.router,
        admin_stats.router,
        user_promo.router,
        user_help.router,
        user_referral.router,
        user_billing.router,
        user_qrcode.router,
        user_payment.router,
        user_signin.router,
        promo_router
    )

    # Запуск планировщика задач (сбор статистики)
    start_scheduler()
    setup_promo_scheduler()

    # 4. Запуск
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("🛑 Бот остановлен пользователем")