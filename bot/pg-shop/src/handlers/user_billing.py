from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.database.requests import get_billing_records, get_user

router = Router()

async def build_billing_text(user_id: int) -> str:
    records = await get_billing_records(user_id, limit=15)
    user = await get_user(user_id)
    balance = user.balance if user else 0

    text = "📄 <b>账单记录</b>（最近15条）\n"
    text += "💰 余额：<b>" + str(balance) + " ¥</b>\n\n"
    text += "━━━━━━━━━━━━\n\n"

    if not records:
        text += "暂无消费记录"
    else:
        for r in records:
            amount = r.amount or 0
            desc = r.description or "操作"
            date = r.created_at.strftime("%m-%d %H:%M") if r.created_at else ""

            if amount > 0:
                icon = "🟢"
                amount_str = "+" + str(amount) + " ¥"
            else:
                icon = "🔻"
                amount_str = str(amount) + " ¥"

            text += icon + " <b>" + amount_str + "</b>   " + desc + "\n"
            text += "   🕒 " + date + "\n\n"

    return text

@router.message(F.text == "📄 账单记录")
async def billing_from_menu(message: Message, t, lang):
    text = await build_billing_text(message.from_user.id)
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 充值余额", callback_data="top_up_menu")
    builder.button(text="🔙 返回", callback_data="back_to_profile")
    builder.adjust(1)
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data == "billing_records")
async def show_billing(callback: CallbackQuery, t, lang):
    text = await build_billing_text(callback.from_user.id)
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 充值余额", callback_data="top_up_menu")
    builder.button(text="🔙 返回", callback_data="back_to_profile")
    builder.adjust(1)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()
