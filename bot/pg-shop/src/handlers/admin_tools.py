from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from contextlib import suppress
from loguru import logger

from src.config import settings
from src.database.requests import (
    get_stats, get_user, get_user_by_username, get_all_users_ids,
    update_user_balance, create_promo_code, get_user_subscriptions,
    get_all_promos, delete_promo, get_promo_by_id
)
from src.keyboards.builders import (
    admin_main_kb, admin_back_kb, admin_user_action_kb, admin_promo_type_kb,
    admin_promos_main_kb, admin_promos_list_kb, admin_promo_view_kb
)

router = Router()

class AdminStates(StatesGroup):
    find_user = State()
    add_balance = State()
    broadcast_text = State()
    create_promo_code = State()
    create_promo_value = State()
    create_promo_uses = State()

@router.message(Command("admin"), F.from_user.id.in_(settings.ADMIN_IDS))
async def admin_panel(message: Message, state: FSMContext):
    await state.clear()
    total_users, active_subs = await get_stats()
    text = (
        "<b>👮 管理员面板</b>\n\n"
        "👥 总用户数：<b>" + str(total_users) + "</b>\n"
        "💎 活跃订阅数：<b>" + str(active_subs) + "</b>\n\n"
        "请选择操作："
    )
    await message.answer(text, reply_markup=admin_main_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_home")
async def admin_home_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    total_users, active_subs = await get_stats()
    text = (
        "<b>👮 管理员面板</b>\n\n"
        "👥 总用户数：<b>" + str(total_users) + "</b>\n"
        "💎 活跃订阅数：<b>" + str(active_subs) + "</b>\n\n"
        "请选择操作："
    )
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(text, reply_markup=admin_main_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_users")
async def admin_users_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "👥 <b>用户管理</b>\n\n请发送用户的 <b>ID</b> 或 <b>@用户名</b>。",
        reply_markup=admin_back_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.find_user)

@router.message(AdminStates.find_user)
async def find_user_handler(message: Message, state: FSMContext):
    from src.services.marzban_api import api as marz_api
    from datetime import datetime as dt
    import aiohttp as aio

    query = message.text.strip()
    user = None
    if query.isdigit():
        user = await get_user(int(query))
    else:
        user = await get_user_by_username(query)

    if not user:
        await message.answer("❌ 未找到用户，请重试或点击返回。", reply_markup=admin_back_kb("admin_users"))
        return

    subs = await get_user_subscriptions(user.id)
    now = dt.now()
    active_subs = [s for s in subs if s.expires_at > now]
    best_sub = sorted(active_subs, key=lambda s: s.expires_at, reverse=True)[0] if active_subs else None

    used_gb = 0
    sub_detail = ""
    if best_sub:
        try:
            headers = await marz_api._headers()
            async with aio.ClientSession() as sess:
                async with sess.get(marz_api.host + "/api/user/" + best_sub.marzban_username, headers=headers) as r:
                    d = await r.json()
                    used = d.get("used_traffic") or 0
                    dlimit = d.get("data_limit") or 0
                    used_gb = round(used / 1024**3, 2)
                    limit_gb = round(dlimit / 1024**3, 2) if dlimit else "无限制"
        except Exception:
            used_gb = 0
            limit_gb = "无限制"

        days_left = (best_sub.expires_at - now).days
        expire_str = "无到期时间" if days_left >= 3640 else best_sub.expires_at.strftime("%Y-%m-%d")
        days_str = "永久" if days_left >= 3640 else (str(days_left) + " 天")
        sub_detail = (
            "\n\n<b>最新订阅：</b>"
            "\n  ⏳ 到期：" + expire_str +
            "\n  ⏱ 剩余：" + days_str +
            "\n  📶 已用：" + str(used_gb) + " GB / " + str(limit_gb) + " GB"
        )

    text = (
        "👤 <b>用户信息</b>\n\n"
        "🆔 ID：<code>" + str(user.id) + "</code>\n"
        "👤 用户名：@" + (user.username or "无") + "\n"
        "💰 余额：<b>" + str(user.balance) + "¥</b>\n"
        "💎 活跃订阅：<b>" + str(len(active_subs)) + "</b> 个\n"
        "📶 已用流量：<b>" + str(used_gb) + " GB</b>\n"
        "📅 注册：" + user.created_at.strftime("%Y-%m-%d")
    ) + sub_detail

    await message.answer(text, reply_markup=admin_user_action_kb(user.id), parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data.startswith("admin_user_profile_"))
async def show_user_profile_cb(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[3])
    user = await get_user(user_id)
    if not user:
        await callback.answer("❌ 未找到该用户", show_alert=True)
        return
    subs = await get_user_subscriptions(user.id)
    from datetime import datetime as dt
    now = dt.now()
    active_subs = [s for s in subs if s.expires_at > now]
    text = (
        "👤 <b>用户信息</b>\n\n"
        "🆔 ID：<code>" + str(user.id) + "</code>\n"
        "👤 用户名：@" + (user.username or "无") + "\n"
        "💰 余额：<b>" + str(user.balance) + "¥</b>\n"
        "💎 活跃订阅：<b>" + str(len(active_subs)) + "</b> 个\n"
        "📅 注册：" + user.created_at.strftime("%Y-%m-%d")
    )
    await callback.message.edit_text(text, reply_markup=admin_user_action_kb(user.id), parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data.startswith("admin_add_balance_"))
async def ask_balance_amount(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[3])
    await state.update_data(target_user_id=user_id)
    await callback.message.edit_text(
        "💰 请输入要为用户 <code>" + str(user_id) + "</code> 充值的金额：\n（输入负数可扣除余额）",
        reply_markup=admin_back_kb("admin_user_profile_" + str(user_id)),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.add_balance)

@router.message(AdminStates.add_balance)
async def process_add_balance(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
        data = await state.get_data()
        user_id = data["target_user_id"]
        await update_user_balance(user_id, amount)
        await message.answer(
            "✅ 已成功将用户 " + str(user_id) + " 的余额修改 " + str(amount) + "¥。",
            reply_markup=admin_back_kb("admin_user_profile_" + str(user_id))
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ 请输入有效数字。")

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✉️ <b>群发消息</b>\n\n请发送要群发的内容（支持图片/视频）。",
        reply_markup=admin_back_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.broadcast_text)

@router.message(AdminStates.broadcast_text)
async def broadcast_process(message: Message, state: FSMContext):
    users = await get_all_users_ids()
    count = 0
    status_msg = await message.answer("⏳ 正在向 " + str(len(users)) + " 位用户发送消息...")
    for user_id in users:
        try:
            await message.copy_to(chat_id=user_id)
            count += 1
        except Exception:
            pass
    await status_msg.edit_text("✅ 群发完成！\n成功发送：" + str(count) + " / " + str(len(users)))
    await state.clear()

@router.callback_query(F.data == "admin_promos")
async def promo_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎟 <b>优惠码管理</b>\n\n请选择操作：",
        reply_markup=admin_promos_main_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_promo_create_start")
async def promo_create_type(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎟 <b>创建优惠码</b>\n\n请选择奖励类型：",
        reply_markup=admin_promo_type_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("create_promo_"))
async def promo_ask_code(callback: CallbackQuery, state: FSMContext):
    p_type = callback.data.split("_")[2]
    await state.update_data(promo_type="balance" if p_type == "balance" else "days")
    await callback.message.edit_text(
        "✍️ <b>请输入优惠码名称</b>（例如：<code>SALE2024</code>）：",
        reply_markup=admin_back_kb("admin_promo_create_start"),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.create_promo_code)

@router.message(AdminStates.create_promo_code)
async def promo_ask_value(message: Message, state: FSMContext):
    await state.update_data(promo_code=message.text.strip())
    data = await state.get_data()
    p_type_text = "充值金额（¥）" if data["promo_type"] == "balance" else "天数"
    await message.answer(
        "🔢 请输入" + p_type_text + "（数字）：",
        reply_markup=admin_back_kb("admin_promo_create_start")
    )
    await state.set_state(AdminStates.create_promo_value)

@router.message(AdminStates.create_promo_value)
async def promo_ask_uses(message: Message, state: FSMContext):
    try:
        value = int(message.text)
        await state.update_data(promo_value=value)
        await message.answer(
            "🔢 <b>请输入最大使用次数</b>（数字）：\n0 = 无限次使用",
            reply_markup=admin_back_kb("admin_promos"),
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.create_promo_uses)
    except ValueError:
        await message.answer("❌ 请输入数字。")

@router.message(AdminStates.create_promo_uses)
async def promo_finish(message: Message, state: FSMContext):
    try:
        max_uses = int(message.text)
        if max_uses < 0:
            raise ValueError
        data = await state.get_data()
        success = await create_promo_code(data["promo_code"], data["promo_type"], data["promo_value"], max_uses=max_uses)
        if success:
            uses_text = "无限" if max_uses == 0 else str(max_uses)
            type_map = {"balance": "💰 余额充值", "days": "🗓 天数兑换", "subscription": "🎁 赠送订阅"}
            type_display = type_map.get(data["promo_type"], data["promo_type"])
            await message.answer(
                "✅ 优惠码 <code>" + data["promo_code"] + "</code> 创建成功！\n"
                "类型：" + type_display + "\n"
                "数值：" + str(data["promo_value"]) + "\n"
                "使用次数：" + uses_text,
                reply_markup=admin_promos_main_kb(),
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ 该优惠码已存在！", reply_markup=admin_back_kb("admin_promos"))
        await state.clear()
    except ValueError:
        await message.answer("❌ 请输入非负数。")

@router.callback_query(F.data == "admin_promo_list")
async def promo_list(callback: CallbackQuery):
    promos = await get_all_promos()
    if not promos:
        await callback.message.edit_text(
            "📜 <b>活跃优惠码列表</b>\n\n列表为空。",
            reply_markup=admin_back_kb("admin_promos"),
            parse_mode="HTML"
        )
        return
    await callback.message.edit_text(
        "📜 <b>活跃优惠码列表</b>\n点击优惠码进行管理：",
        reply_markup=admin_promos_list_kb(promos),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("admin_promo_view_"))
async def promo_view(callback: CallbackQuery):
    promo_id = int(callback.data.split("_")[3])
    promo = await get_promo_by_id(promo_id)
    if not promo:
        await callback.answer("优惠码不存在", show_alert=True)
        await promo_list(callback)
        return
    uses_str = str(promo.current_uses) + " / " + (str(promo.max_uses) if promo.max_uses > 0 else "∞")
    type_map = {"balance": "💰 余额充值", "days": "🗓 天数兑换", "subscription": "🎁 赠送订阅"}
    type_display = type_map.get(promo.type, promo.type)
    text = (
        "🎟 <b>优惠码：</b><code>" + promo.code + "</code>\n\n"
        "类型：<b>" + type_display + "</b>\n"
        "数值：<b>" + str(promo.value) + "</b>\n"
        "使用次数：<b>" + uses_str + "</b>"
    )
    await callback.message.edit_text(text, reply_markup=admin_promo_view_kb(promo.id), parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_promo_delete_"))
async def promo_delete_handler(callback: CallbackQuery):
    promo_id = int(callback.data.split("_")[3])
    try:
        await delete_promo(promo_id)
        await callback.answer("✅ 优惠码已删除")
        await promo_list(callback)
    except Exception as e:
        logger.exception("删除优惠码 " + str(promo_id) + " 时出错")
        await callback.answer("❌ 删除失败，请查看日志。", show_alert=True)


@router.callback_query(F.data == "admin_stats_full")
async def admin_stats_full(callback: CallbackQuery, t, lang):
    import sqlite3
    from datetime import datetime, timedelta
    from src.services.marzban_api import api
    import aiohttp

    conn = sqlite3.connect('/opt/pg-shop/shop.db')
    now = datetime.now()
    today = now.date().isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()
    month_ago = (now - timedelta(days=30)).isoformat()

    # 用户统计
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    new_today = conn.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (today,)).fetchone()[0]
    new_week = conn.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (week_ago,)).fetchone()[0]
    new_month = conn.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (month_ago,)).fetchone()[0]

    # 订阅统计
    active_subs = conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM subscriptions WHERE expires_at > ?",
        (now.isoformat(),)
    ).fetchone()[0]
    time_subs = conn.execute(
        "SELECT COUNT(*) FROM subscriptions WHERE plan_type='time' AND expires_at > ?",
        (now.isoformat(),)
    ).fetchone()[0]
    traffic_subs = conn.execute(
        "SELECT COUNT(*) FROM subscriptions WHERE plan_type='traffic' AND expires_at > ?",
        (now.isoformat(),)
    ).fetchone()[0]

    # 收入统计
    total_income = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE amount > 0"
    ).fetchone()[0]
    today_income = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE amount > 0 AND created_at >= ?",
        (today,)
    ).fetchone()[0]
    week_income = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE amount > 0 AND created_at >= ?",
        (week_ago,)
    ).fetchone()[0]
    month_income = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE amount > 0 AND created_at >= ?",
        (month_ago,)
    ).fetchone()[0]

    # 签到统计
    total_signins = conn.execute("SELECT COUNT(*) FROM sign_in_records").fetchone()[0]
    today_signins = conn.execute(
        "SELECT COUNT(*) FROM sign_in_records WHERE sign_date=?", (today,)
    ).fetchone()[0]

    # 余额统计
    total_balance = conn.execute("SELECT COALESCE(SUM(balance),0) FROM users").fetchone()[0]

    conn.close()

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 刷新", callback_data="admin_stats_full")
    builder.button(text="🔙 返回", callback_data="admin_home")
    builder.adjust(2)

    text = (
        "╔══════════════════╗\n"
        "      📊 运营统计\n"
        "╚══════════════════╝\n\n"
        "━━━━━━━━━━━━\n"
        "👥 <b>用户数据</b>\n\n"
        "总用户：<b>" + str(total_users) + "</b>\n"
        "今日新增：<b>" + str(new_today) + "</b>\n"
        "本周新增：<b>" + str(new_week) + "</b>\n"
        "本月新增：<b>" + str(new_month) + "</b>\n\n"
        "━━━━━━━━━━━━\n"
        "📦 <b>订阅数据</b>\n\n"
        "活跃用户：<b>" + str(active_subs) + "</b>\n"
        "时间套餐：<b>" + str(time_subs) + "</b>\n"
        "流量套餐：<b>" + str(traffic_subs) + "</b>\n\n"
        "━━━━━━━━━━━━\n"
        "💰 <b>收入数据</b>\n\n"
        "今日收入：<b>" + str(today_income) + "¥</b>\n"
        "本周收入：<b>" + str(week_income) + "¥</b>\n"
        "本月收入：<b>" + str(month_income) + "¥</b>\n"
        "累计收入：<b>" + str(total_income) + "¥</b>\n\n"
        "━━━━━━━━━━━━\n"
        "📅 <b>签到数据</b>\n\n"
        "今日签到：<b>" + str(today_signins) + "</b> 人\n"
        "累计签到：<b>" + str(total_signins) + "</b> 次\n\n"
        "━━━━━━━━━━━━\n"
        "💵 <b>余额数据</b>\n\n"
        "用户总余额：<b>" + str(total_balance) + "¥</b>\n\n"
        "🕒 更新时间：" + now.strftime("%m-%d %H:%M")
    )

    # 从 Marzban 获取流量统计
    try:
        from src.database.core import async_session
        from src.database.models import Subscription
        from sqlalchemy import select
        from src.services.marzban_api import api
        import aiohttp

        async with async_session() as session:
            subs = (await session.scalars(select(Subscription))).all()

        total_used = 0
        checked = set()
        headers = await api._headers()

        async with aiohttp.ClientSession() as sess:
            for sub in subs:
                if not sub.marzban_username or sub.marzban_username in checked:
                    continue
                checked.add(sub.marzban_username)
                try:
                    async with sess.get(
                        api.host + "/api/user/" + sub.marzban_username,
                        headers=headers
                    ) as r:
                        if r.status == 200:
                            d = await r.json()
                            total_used += d.get("used_traffic") or 0
                except:
                    pass

        total_used_gb = round(total_used / 1024**3, 2)
        text += (
            "\n━━━━━━━━━━━━\n"
            "📡 <b>流量统计</b>\n\n"
            "全部用户已用流量：<b>" + str(total_used_gb) + " GB</b>\n"
            "活跃用户数：<b>" + str(len(checked)) + "</b>\n"
        )
    except Exception as e:
        text += "\n⚠️ 流量统计获取失败"

    from contextlib import suppress
    from aiogram.exceptions import TelegramBadRequest
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()
