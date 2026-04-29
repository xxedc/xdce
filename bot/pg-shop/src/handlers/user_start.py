from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from src.keyboards.reply import get_main_kb
from src.database.requests import add_user, get_user, get_user_subscriptions

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, t, lang, state=None):
    if state:
        await state.clear()
    user_id = message.from_user.id
    await add_user(user_id, message.from_user.username, lang)

    # 处理邀请参数 /start ref_123456
    args = message.text.split() if message.text else []
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].replace("ref_", ""))
            if referrer_id != user_id:
                from src.database.requests import set_referrer
                await set_referrer(user_id, referrer_id)
        except ValueError:
            pass

    user = await get_user(user_id)
    subs = await get_user_subscriptions(user_id)
    has_active_sub = any(sub.expires_at > datetime.now() for sub in subs)
    is_trial_used = (user.is_trial_used if user else False)

    await message.answer(
        t("start_msg"),
        reply_markup=get_main_kb(lang, is_trial_used),
        parse_mode="HTML"
    )