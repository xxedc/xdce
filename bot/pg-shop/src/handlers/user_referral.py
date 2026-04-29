from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.database.requests import get_user, get_referral_stats

router = Router()

@router.message(F.text == "👥 邀请返利")
async def referral_menu(message: Message, t, lang):
    user_id = message.from_user.id
    stats = await get_referral_stats(user_id)
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    count = stats["count"] if stats else 0
    earnings = stats["earnings"] if stats else 0

    text = (
        "👥 <b>邀请好友返佣</b>\n\n"
        "📋 <b>返佣规则：</b>\n"
        "  • 好友通过你的链接注册并购买\n"
        "  • 你立即获得购买金额 <b>10%</b> 余额返佣\n"
        "  • 同时获得 <b>7天</b> 订阅时间延长\n\n"
        "📊 <b>我的邀请记录：</b>\n"
        "  • 成功邀请：<b>" + str(count) + " 人</b>\n"
        "  • 累计返佣：<b>" + str(earnings) + " ¥</b>\n\n"
        "🔗 <b>我的邀请链接：</b>\n"
        "<code>" + ref_link + "</code>\n\n"
        "💡 复制链接发给好友，好友购买后自动到账！"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📤 分享给好友", switch_inline_query=ref_link)
    builder.adjust(1)

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
