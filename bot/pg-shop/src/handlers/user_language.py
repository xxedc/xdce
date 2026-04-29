from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from src.keyboards.builders import language_kb
from src.database.requests import update_user_language
from src.utils.translations import get_text
from src.keyboards.reply import get_main_kb

router = Router()

@router.message(Command("language"))
async def cmd_language(message: Message, t):
    await message.answer(t("choose_lang"), reply_markup=language_kb())

@router.callback_query(F.data.startswith("lang_"))
async def process_language_selection(callback: CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_id = callback.from_user.id

    await update_user_language(user_id, lang_code)

    # 检查是否已使用试用
    from src.database.requests import get_user, get_user_subscriptions
    from datetime import datetime
    user = await get_user(user_id)
    subs = await get_user_subscriptions(user_id)
    has_active = any(s.expires_at > datetime.now() for s in subs)
    is_trial_used = (user.is_trial_used if user else False) or has_active

    text = get_text(lang_code, "lang_changed")
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=get_main_kb(lang_code, is_trial_used=is_trial_used))
    await callback.answer()