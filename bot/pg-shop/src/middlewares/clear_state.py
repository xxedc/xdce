from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

MAIN_MENU_TEXTS = [
    "🚀 开通订阅", "📦 我的订阅", "💰 个人中心",
    "👥 邀请返利", "📄 账单记录", "🆘 帮助中心", "🎁 免费试用"
]

class ClearStateMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, Message) and event.text in MAIN_MENU_TEXTS:
            state: FSMContext = data.get("state")
            if state:
                current = await state.get_state()
                if current:
                    await state.clear()
        return await handler(event, data)
