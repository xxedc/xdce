from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.services.payment import payment
from src.database.requests import get_user, update_user_balance, add_billing_record
from src.database.core import async_session
from src.database.models import User
from sqlalchemy import select
import uuid
import json

router = Router()

# 充值金额选项（CNY 对应 USDT 汇率约 7.2）
# 1U = 7.2¥ 汇率
# 套餐价格：1个月15¥、3个月40¥、6个月75¥、12个月140¥、流量包35¥
TOP_UP_OPTIONS = [
    (15,  2.1, "🗓 1个月套餐   15¥ = 2.1 USDT"),
    (35,  4.9, "📦 流量包500GB 35¥ = 4.9 USDT"),
    (40,  5.6, "🗓 3个月套餐   40¥ = 5.6 USDT"),
    (75,  10.4,"🗓 6个月套餐   75¥ = 10.4 USDT"),
    (140, 19.4,"🗓 12个月套餐 140¥ = 19.4 USDT"),
    (200, 27.8,"💰 充值200¥   = 27.8 USDT"),
]

@router.callback_query(F.data == "top_up_menu")
async def top_up_menu(callback: CallbackQuery, t, lang):
    from src.handlers.user_buy import get_usdt_rate
    user = await get_user(callback.from_user.id)
    balance = user.balance if user else 0
    rate = await get_usdt_rate()

    def u(cny): return round(cny / rate, 1)

    builder = InlineKeyboardBuilder()
    quick_options = [
        (15,  "🗓 1个月   15¥ = " + str(u(15)) + " USDT"),
        (40,  "🗓 3个月   40¥ = " + str(u(40)) + " USDT"),
        (75,  "🗓 6个月   75¥ = " + str(u(75)) + " USDT"),
        (140, "🗓 12个月 140¥ = " + str(u(140)) + " USDT"),
        (35,  "📦 流量包  35¥ = " + str(u(35)) + " USDT"),
    ]
    for cny, label in quick_options:
        usdt = u(cny)
        builder.button(text=label, callback_data="pay_create_" + str(cny) + "_" + str(usdt))
    builder.button(text="✏️ 自定义金额", callback_data="topup_custom")
    builder.button(text="🔙 返回", callback_data="back_to_profile")
    builder.adjust(1)

    text = (
        "╔══════════════╗\n"
        "      余额充值\n"
        "╚══════════════╝\n\n"
        "当前余额：<b>" + str(balance) + " ¥</b>\n"
        "实时汇率（Binance）：<b>1 USDT ≈ " + str(rate) + " ¥</b>\n\n"
        "━━━━━━━━━━━━\n\n"
        "支持：USDT（TRC20） / TRX / BTC / ETH\n\n"
        "━━━━━━━━━━━━\n\n"
        "可选择套餐充值或自定义金额"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "topup_custom")
async def topup_custom(callback: CallbackQuery, t, lang):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 返回", callback_data="top_up_menu")
    builder.adjust(1)
    await callback.message.edit_text(
        "✏️ <b>自定义充值</b>\n\n"
        "汇率：<b>1 USDT ≈ 7.2 ¥</b>\n\n"
        "━━━━━━━━━━━━\n\n"
        "请输入充值金额（¥）\n"
        "例如：100 = 13.9 USDT\n\n"
        "━━━━━━━━━━━━\n\n"
        "范围：10 ¥ - 10000 ¥\n\n"
        "👇 <b>发送数字即可</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.message(F.text.regexp(r"^\d+$"))
async def handle_topup_amount(message, t, lang):
    """用户直接输入数字金额进行充值"""
    amount_cny = int(message.text)

    if amount_cny < 10:
        await message.answer("❌ 最低充值金额为 10¥")
        return
    if amount_cny > 10000:
        await message.answer("❌ 单次充值最高 10000¥")
        return

    usdt = round(amount_cny / 7.2, 2)

    builder = InlineKeyboardBuilder()
    builder.button(
        text="💳 确认支付 " + str(usdt) + " USDT",
        callback_data="pay_create_" + str(amount_cny) + "_" + str(usdt)
    )
    builder.button(text="🔙 取消", callback_data="back_to_profile")
    builder.adjust(1)

    await message.answer(
        "💰 <b>充值确认</b>\n\n"
        "充值金额：<b>" + str(amount_cny) + "¥</b>\n"
        "需支付：<b>" + str(usdt) + " USDT</b>\n\n"
        "确认后生成支付地址",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("pay_create_"))
async def create_payment(callback: CallbackQuery, t, lang):
    parts = callback.data.split("_")
    cny = int(parts[2])
    usdt = float(parts[3])
    user_id = callback.from_user.id

    await callback.answer("⏳ 正在生成支付地址...")

    # 生成唯一订单号
    order_id = uuid.uuid4().hex[:16]  # 短订单号，最大16字符

    try:
        result = await payment.create_invoice(
            amount=usdt,
            currency="USDT",
            order_id=order_id,
            user_id=user_id
        )

        if result.get("state") == 0:
            data = result.get("result", {})
            pay_url = data.get("url") or ""
            pay_address = data.get("address") or "待确认"
            pay_amount = data.get("payer_amount") or data.get("amount") or str(usdt)
            pay_currency = data.get("payer_currency") or data.get("currency") or "USDT"
            uuid_val = data.get("uuid") or ""

            builder = InlineKeyboardBuilder()
            if pay_url:
                builder.button(text="💳 点击支付", url=pay_url)
            # 存储映射关系，callback只传短key
            short_key = order_id[:12]
            builder.button(text="🔄 检查支付状态", callback_data="pc_" + short_key + "_" + str(cny))
            builder.button(text="🔙 取消", callback_data="top_up_menu")
            builder.adjust(1)

            text = (
                "💳 <b>USDT 支付订单</b>\n\n"
                "充值金额：<b>" + str(cny) + "¥</b>\n"
                "应付：<b>" + str(pay_amount or usdt) + " " + str(pay_currency or "USDT") + "</b>\n\n"
                "📋 <b>支付地址：</b>\n"
                "<code>" + pay_address + "</code>\n\n"
                "⏰ 有效期：60分钟\n\n"
                "✅ 付款后点击「检查支付状态」确认到账\n"
                "💡 或点击「点击支付」直接跳转支付页面"
            )
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        else:
            error = result.get("message", "未知错误")
            await callback.message.edit_text(
                "❌ 创建支付失败：" + str(error) + "\n\n请稍后重试",
                reply_markup=InlineKeyboardBuilder().button(text="🔙 返回", callback_data="top_up_menu").as_markup()
            )
    except Exception as e:
        await callback.message.edit_text(
            "❌ 支付系统错误，请稍后重试\n错误：" + str(e),
            reply_markup=InlineKeyboardBuilder().button(text="🔙 返回", callback_data="top_up_menu").as_markup()
        )


@router.callback_query(F.data.startswith("pc_"))
async def check_payment_status(callback: CallbackQuery, t, lang):
    parts = callback.data.split("_")
    order_id = parts[1]
    cny = int(parts[2])
    uuid_val = order_id  # 用 order_id 查询
    user_id = callback.from_user.id

    await callback.answer("⏳ 检查中...")

    try:
        result = await payment.check_payment(order_id)
        data = result.get("result", {})
        status = data.get("payment_status", "")

        if status == "paid" or status == "paid_over":
            # 支付成功，充值余额
            async with async_session() as session:
                user = await session.scalar(select(User).where(User.id == user_id))
                if user:
                    user.balance += cny
                    await session.commit()
                    new_balance = user.balance

            await add_billing_record(user_id, cny, "topup", "USDT充值 +" + str(cny) + "¥")

            builder = InlineKeyboardBuilder()
            builder.button(text="🚀 立即购买", callback_data="start_buy")
            builder.button(text="🔙 返回账户", callback_data="back_to_profile")
            builder.adjust(1)

            await callback.message.edit_text(
                "✅ <b>充值成功！</b>\n\n"
                "充值金额：<b>" + str(cny) + "¥</b>\n"
                "当前余额：<b>" + str(new_balance) + "¥</b>",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )

        elif status == "cancel" or status == "fail":
            await callback.message.edit_text(
                "❌ 支付已取消或失败\n请重新发起支付",
                reply_markup=InlineKeyboardBuilder().button(text="🔙 返回", callback_data="top_up_menu").as_markup()
            )
        else:
            # 等待支付
            builder = InlineKeyboardBuilder()
            builder.button(text="🔄 继续检查", callback_data=callback.data)
            builder.button(text="🔙 取消", callback_data="top_up_menu")
            builder.adjust(1)

            status_map = {
                "process": "处理中",
                "check": "确认中",
                "": "等待付款"
            }
            status_zh = status_map.get(status, status)

            await callback.message.edit_text(
                "⏳ <b>等待支付确认</b>\n\n"
                "状态：" + status_zh + "\n\n"
                "付款后请等待1-3分钟再检查",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
    except Exception as e:
        await callback.answer("检查失败: " + str(e), show_alert=True)
