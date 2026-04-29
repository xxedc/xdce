from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from src.utils.translations import get_text
from src.database.requests import get_user

class I18nMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        tg_user: User = data.get("event_from_user")
        db_user = await get_user(tg_user.id) if tg_user else None
        
        if db_user and db_user.language_code:
            # 1. Приоритет: Язык из базы данных (если юзер уже есть)
            lang_code = db_user.language_code
        else:
            # 2. Приоритет: Язык из настроек Telegram
            # Если язык не поддерживается, ставим 'en'
            lang_code = tg_user.language_code if tg_user and tg_user.language_code in ["ru", "en", "zh"] else "zh"
        
        # Передаем функцию перевода в хендлер
        data["t"] = lambda text_key, **kwargs: get_text(lang_code, text_key, **kwargs)
        data["lang"] = lang_code
        
        return await handler(event, data)