from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from src.utils.translations import get_text

def get_main_kb(lang: str = "zh", is_trial_used: bool = False):
    keyboard = [
        [KeyboardButton(text="🚀 开通订阅")],
        [KeyboardButton(text="📅 每日签到"), KeyboardButton(text="📦 我的订阅")],
        [KeyboardButton(text="💰 个人中心"), KeyboardButton(text="👥 邀请返利")],
        [KeyboardButton(text="📄 账单记录"), KeyboardButton(text="🆘 帮助中心")],
    ]

    if not is_trial_used:
        keyboard.insert(1, [KeyboardButton(text="🎁 免费试用")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="请选择操作..."
    )
