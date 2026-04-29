from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, date, timedelta
import sqlite3
from loguru import logger

router = Router()

CHANNEL_ID = -1003798316924  # DC免费VPN群组

# 签到奖励配置（连续天数 -> GB）
SIGNIN_REWARDS = {
    1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2, 7: 2
}
MONTHLY_GB_LIMIT = 50  # 每月上限50GB
MONTHLY_BALANCE_REWARD = 0  # 不再发余额  # 超出上限后每次签到奖励1¥

def get_db():
    return sqlite3.connect('/opt/pg-shop/shop.db')

def get_reward_for_day(consecutive: int) -> int:
    day = consecutive % 7
    if day == 0:
        day = 7
    return SIGNIN_REWARDS.get(day, 2)

async def get_user_sign_stats(user_id: int) -> dict:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM user_sign_stats WHERE user_id=?", (user_id,)
    ).fetchone()
    conn.close()

    if not row:
        return {
            "user_id": user_id,
            "total_consecutive": 0,
            "max_consecutive": 0,
            "monthly_gb": 0.0,
            "monthly_reset_date": None,
            "last_sign_date": None,
            "channel_joined": 0,
            "channel_reward_given": 0
        }
    return {
        "user_id": row[0],
        "total_consecutive": row[1],
        "max_consecutive": row[2],
        "monthly_gb": row[3],
        "monthly_reset_date": row[4],
        "last_sign_date": row[5],
        "channel_joined": row[6],
        "channel_reward_given": row[7]
    }

async def do_sign_in(user_id: int) -> dict:
    """执行签到，返回奖励信息"""
    conn = get_db()
    today = date.today()
    stats = await get_user_sign_stats(user_id)

    # 检查今天是否已签到
    already = conn.execute(
        "SELECT id FROM sign_in_records WHERE user_id=? AND sign_date=?",
        (user_id, today.isoformat())
    ).fetchone()

    if already:
        conn.close()
        return {"already": True}

    # 计算连续天数
    last_date = stats["last_sign_date"]
    consecutive = stats["total_consecutive"]

    if last_date:
        last = date.fromisoformat(last_date)
        if (today - last).days == 1:
            consecutive += 1
        elif (today - last).days > 1:
            consecutive = 1
    else:
        consecutive = 1

    # 检查月流量重置
    monthly_gb = stats["monthly_gb"]
    reset_date = stats["monthly_reset_date"]
    if not reset_date or date.fromisoformat(reset_date).month != today.month:
        monthly_gb = 0.0
        reset_date = today.replace(day=1).isoformat()

    # 计算奖励
    reward_gb = 0.0
    reward_balance = 0

    if monthly_gb < MONTHLY_GB_LIMIT:
        day_reward = get_reward_for_day(consecutive)
        remaining = MONTHLY_GB_LIMIT - monthly_gb
        reward_gb = min(day_reward, remaining)
        monthly_gb += reward_gb
    else:
        reward_balance = MONTHLY_BALANCE_REWARD

    # 连续14天额外奖励
    extra_gb = 0
    if consecutive == 14:
        extra_gb = min(10, MONTHLY_GB_LIMIT - monthly_gb)
        monthly_gb += extra_gb
        reward_gb += extra_gb
    elif consecutive == 30:
        extra_gb = min(20, MONTHLY_GB_LIMIT - monthly_gb)
        monthly_gb += extra_gb
        reward_gb += extra_gb

    # 保存签到记录
    conn.execute(
        "INSERT OR IGNORE INTO sign_in_records (user_id, sign_date, consecutive_days, reward_gb, reward_balance) VALUES (?,?,?,?,?)",
        (user_id, today.isoformat(), consecutive, reward_gb, reward_balance)
    )

    # 更新统计
    max_cons = max(stats["max_consecutive"], consecutive)
    conn.execute("""
        INSERT INTO user_sign_stats (user_id, total_consecutive, max_consecutive, monthly_gb, monthly_reset_date, last_sign_date, channel_joined, channel_reward_given)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
            total_consecutive=?,
            max_consecutive=?,
            monthly_gb=?,
            monthly_reset_date=?,
            last_sign_date=?
    """, (
        user_id, consecutive, max_cons, monthly_gb, reset_date, today.isoformat(),
        stats["channel_joined"], stats["channel_reward_given"],
        consecutive, max_cons, monthly_gb, reset_date, today.isoformat()
    ))

    # 给用户加流量（更新数据库订阅）
    if reward_gb > 0:
        existing = conn.execute(
            "SELECT id, traffic_gb FROM subscriptions WHERE user_id=? AND plan_type='traffic'",
            (user_id,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE subscriptions SET traffic_gb = COALESCE(traffic_gb,0) + ? WHERE id=?",
                (int(reward_gb), existing[0])
            )
            new_traffic_gb = (existing[1] or 0) + int(reward_gb)
        else:
            from datetime import datetime as dt
            expire = (dt.now() + timedelta(days=3650)).strftime('%Y-%m-%d %H:%M:%S')
            # 用和时间套餐相同的 marzban_username
            existing_time = conn.execute(
                "SELECT marzban_username FROM subscriptions WHERE user_id=? AND plan_type='time' LIMIT 1",
                (user_id,)
            ).fetchone()
            marzban_username = existing_time[0] if existing_time else "user_" + str(user_id)
            conn.execute("""
                INSERT INTO subscriptions (user_id, vless_key, server_id, expires_at, plan_type, traffic_gb, marzban_username)
                VALUES (?,?,?,?,?,?,?)
            """, (user_id, "", 2, expire, "traffic", int(reward_gb), marzban_username))
            new_traffic_gb = int(reward_gb)

        conn.commit()

        # 同步到 PasarGuard:叠加流量(不覆盖)- 只查不写,避免 closed db
        _mz_username_for_sync = None
        try:
            row = conn.execute(
                "SELECT marzban_username FROM subscriptions WHERE user_id=? AND marzban_username != '' ORDER BY id DESC LIMIT 1",
                (user_id,)
            ).fetchone()
            if row and row[0]:
                _mz_username_for_sync = row[0]
        except Exception:
            pass

    # 给用户加余额
    if reward_balance > 0:
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE id=?",
            (reward_balance, user_id)
        )

    # 在关闭 db 前查最新 marzban_username(优先 user_xxx)
    _mz_user_for_sync = None
    if reward_gb > 0:
        try:
            _row = conn.execute(
                "SELECT marzban_username FROM subscriptions WHERE user_id=? AND marzban_username != '' ORDER BY CASE WHEN marzban_username LIKE 'user_%' THEN 0 ELSE 1 END, id DESC LIMIT 1",
                (user_id,)
            ).fetchone()
            if _row and _row[0]:
                _mz_user_for_sync = _row[0]
        except Exception:
            pass

    conn.commit()
    conn.close()

    # 同步到 PasarGuard(在 db 关闭后执行,避免 closed db 错误)
    if reward_gb > 0 and _mz_user_for_sync:
        try:
            import asyncio as _aio
            from src.services.marzban_api import api as _api
            _loop = _aio.get_event_loop()
            _loop.create_task(_api.add_data_limit_gb(_mz_user_for_sync, reward_gb))
            logger.info(f"📊 签到 +{reward_gb}GB 已同步到 PasarGuard: {_mz_user_for_sync}")
        except Exception as _e:
            logger.error(f"签到同步失败: {_e}")

    return {
        "already": False,
        "consecutive": consecutive,
        "reward_gb": reward_gb,
        "reward_balance": reward_balance,
        "monthly_gb": monthly_gb,
        "extra_gb": extra_gb,
        "monthly_limit_reached": monthly_gb >= MONTHLY_GB_LIMIT
    }


@router.message(F.text == "📅 每日签到")
async def cmd_signin(message: Message):
    user_id = message.from_user.id
    result = await do_sign_in(user_id)

    if result.get("already"):
        stats = await get_user_sign_stats(user_id)
        tomorrow = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
        hours_left = int((tomorrow - datetime.now()).seconds / 3600)

        builder = InlineKeyboardBuilder()
        builder.button(text="📊 签到统计", callback_data="signin_stats")
        builder.button(text="🎁 入群领流量包", callback_data="join_channel")
        builder.button(text="✅ 已分享，领取 +1GB（每日2次）", callback_data="share_reward")
        builder.button(text="📤 分享给好友", url="https://t.me/share/url?url=https://t.me/dcxxe_bot&text=%F0%9F%9A%80%20DC%E5%8A%A0%E9%80%9F%20-%20%E5%9B%BD%E9%99%85VPN%E4%B8%93%E7%BA%BF%0A%E2%9C%85%20%E5%85%A8%E7%90%83%E8%8A%82%E7%82%B9%20%C2%B7%20%E5%8E%9F%E7%94%9FIP%20%C2%B7%20%E7%A8%B3%E5%A6%82%E8%80%81%E7%8B%97%0A%E2%9C%85%20Netflix%20%C2%B7%20Disney%2B%20%E5%8E%9F%E7%94%9F%E8%A7%A3%E9%94%81%0A%E2%9C%85%204K%E6%B2%B9%E7%AE%A1%E4%B8%8D%E5%8D%A1%20%C2%B7%20%E6%B8%B8%E6%88%8F%E4%BD%8E%E5%BB%B6%E8%BF%9F%0A%F0%9F%8E%81%20%E6%96%B0%E4%BA%BA%E6%B3%A8%E5%86%8C%E7%AB%8B%E9%80%81%207%E5%A4%A9%2030GB%20%E4%BD%93%E9%AA%8C%0A%F0%9F%91%87%20%E7%82%B9%E5%87%BB%E7%AB%8B%E5%8D%B3%E5%BC%80%E9%80%9A%0Ahttps%3A//t.me/dcxxe_bot")
        builder.adjust(1)

        await message.answer(
            "✅ <b>今日已签到</b>\n\n"
            "⏰ 距离明日签到还有 <b>" + str(hours_left) + " 小时</b>\n\n"
            "🔥 连续签到：<b>" + str(stats["total_consecutive"]) + " 天</b>\n"
            "📦 本月已获：<b>" + str(round(stats["monthly_gb"], 1)) + " GB</b>",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        return

    consecutive = result["consecutive"]
    reward_gb = result["reward_gb"]
    reward_balance = result["reward_balance"]
    monthly_gb = result["monthly_gb"]

    # 计算下一天奖励
    next_day_reward = get_reward_for_day(consecutive + 1)

    # 进度条（7天周期）
    day_in_week = consecutive % 7 or 7
    progress = "🟡" * day_in_week + "⚪" * (7 - day_in_week)

    builder = InlineKeyboardBuilder()
    builder.button(text="📊 签到统计", callback_data="signin_stats")
    builder.button(text="🎁 入群领流量包", callback_data="join_channel")
    # 分享按钮
    builder.button(text="📤 已分享，领取 +1GB（每日2次）", callback_data="share_reward")
    builder.button(text="📤 分享给好友", url="https://t.me/share/url?url=https://t.me/dcxxe_bot&text=%F0%9F%9A%80%20DC%E5%8A%A0%E9%80%9F%20-%20%E5%9B%BD%E9%99%85VPN%E4%B8%93%E7%BA%BF%0A%E2%9C%85%20%E5%85%A8%E7%90%83%E8%8A%82%E7%82%B9%20%C2%B7%20%E5%8E%9F%E7%94%9FIP%20%C2%B7%20%E7%A8%B3%E5%A6%82%E8%80%81%E7%8B%97%0A%E2%9C%85%20Netflix%20%C2%B7%20Disney%2B%20%E5%8E%9F%E7%94%9F%E8%A7%A3%E9%94%81%0A%E2%9C%85%204K%E6%B2%B9%E7%AE%A1%E4%B8%8D%E5%8D%A1%20%C2%B7%20%E6%B8%B8%E6%88%8F%E4%BD%8E%E5%BB%B6%E8%BF%9F%0A%F0%9F%8E%81%20%E6%96%B0%E4%BA%BA%E6%B3%A8%E5%86%8C%E7%AB%8B%E9%80%81%207%E5%A4%A9%2030GB%20%E4%BD%93%E9%AA%8C%0A%F0%9F%91%87%20%E7%82%B9%E5%87%BB%E7%AB%8B%E5%8D%B3%E5%BC%80%E9%80%9A%0Ahttps%3A//t.me/dcxxe_bot")
    builder.adjust(1)

    if reward_balance > 0:
        reward_text = "💰 本次奖励：<b>+" + str(reward_balance) + "¥</b>（月流量已达上限）"
    else:
        reward_text = "📦 本次奖励：<b>+" + str(reward_gb) + " GB</b>"

    extra_text = ""
    if result.get("extra_gb", 0) > 0:
        if consecutive == 14:
            extra_text = "\n🔥 <b>连续14天特别奖励：+10GB</b>"
        elif consecutive == 30:
            extra_text = "\n🏆 <b>连续30天特别奖励：+20GB</b>"

    text = (
        "📅 <b>签到成功！</b>\n\n"
        + reward_text + extra_text + "\n\n"
        "━━━━━━━━━━━━\n\n"
        "🔥 连续签到：<b>" + str(consecutive) + " 天</b>\n"
        "📊 本周进度：" + progress + "\n"
        "📦 本月已获：<b>" + str(round(monthly_gb, 1)) + " / " + str(MONTHLY_GB_LIMIT) + " GB</b>\n\n"
        "━━━━━━━━━━━━\n\n"
        "⏭ 明日奖励：<b>+" + str(next_day_reward) + " GB</b>\n"
    )

    if day_in_week == 7:
        text += "🎁 <b>连续7天已达成！明日重新开始新周期</b>\n"

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data == "signin_stats")
async def show_signin_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    stats = await get_user_sign_stats(user_id)

    conn = get_db()
    month_start = date.today().replace(day=1).isoformat()
    month_count = conn.execute(
        "SELECT COUNT(*) FROM sign_in_records WHERE user_id=? AND sign_date>=?",
        (user_id, month_start)
    ).fetchone()[0]
    total_count = conn.execute(
        "SELECT COUNT(*) FROM sign_in_records WHERE user_id=?",
        (user_id,)
    ).fetchone()[0]
    conn.close()

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 返回", callback_data="back_to_profile")
    builder.adjust(1)

    await callback.message.edit_text(
        "📊 <b>签到统计</b>\n\n"
        "━━━━━━━━━━━━\n\n"
        "🔥 当前连续：<b>" + str(stats["total_consecutive"]) + " 天</b>\n"
        "🏆 最长连续：<b>" + str(stats["max_consecutive"]) + " 天</b>\n"
        "📅 本月签到：<b>" + str(month_count) + " 次</b>\n"
        "📅 累计签到：<b>" + str(total_count) + " 次</b>\n\n"
        "━━━━━━━━━━━━\n\n"
        "📦 本月已获：<b>" + str(round(stats["monthly_gb"], 1)) + " / " + str(MONTHLY_GB_LIMIT) + " GB</b>\n\n"
        "━━━━━━━━━━━━\n\n"
        "📋 <b>签到奖励规则</b>\n"
        "第1-2天：+5GB/天\n"
        "第3-4天：+8GB/天\n"
        "第5-6天：+10GB/天\n"
        "第7天：  +15GB 🎁\n"
        "连续14天：额外+10GB 🔥\n"
        "连续30天：额外+20GB 🏆\n"
        "月上限达到后:当日不再发放奖励",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "join_channel")
async def join_channel(callback: CallbackQuery):
    user_id = callback.from_user.id
    stats = await get_user_sign_stats(user_id)

    if stats["channel_reward_given"]:
        await callback.answer("✅ 你已领取过频道奖励", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="👥 加入群组 @DCxxeo", url="https://t.me/DCxxeo")
    builder.button(text="✅ 我已加入，领取奖励", callback_data="verify_channel")
    builder.button(text="🔙 返回", callback_data="back_to_profile")
    builder.adjust(1)

    await callback.message.edit_text(
        "🎁 <b>入群领流量包</b>\n\n"
        "━━━━━━━━━━━━\n\n"
        "🎁 加入即可获得：\n"
        "  • <b>+7天</b> 订阅时间\n"
        "  • <b>+20GB</b> 流量包\n\n"
        "━━━━━━━━━━━━\n\n"
        "1️⃣ 点击下方加入频道\n"
        "2️⃣ 加入后点击「我已加入」\n"
        "3️⃣ 自动验证并发放奖励",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "verify_channel")
async def verify_channel(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot = callback.bot

    stats = await get_user_sign_stats(user_id)
    if stats["channel_reward_given"]:
        await callback.answer("✅ 你已领取过频道奖励", show_alert=True)
        return

    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        is_member = member.status in ("member", "administrator", "creator")
    except Exception:
        is_member = False

    if not is_member:
        await callback.answer("❌ 未检测到你加入频道，请先加入再领取", show_alert=True)
        return

    # 发放奖励：+7天订阅 + 20GB
    conn = get_db()
    from datetime import datetime as dt

    # 更新订阅时间
    time_sub = conn.execute(
        "SELECT id, expires_at FROM subscriptions WHERE user_id=? AND plan_type='time'",
        (user_id,)
    ).fetchone()

    if time_sub:
        old_expire = dt.fromisoformat(time_sub[1])
        new_expire = (old_expire if old_expire > dt.now() else dt.now()) + timedelta(days=7)
        conn.execute(
            "UPDATE subscriptions SET expires_at=? WHERE id=?",
            (new_expire.strftime('%Y-%m-%d %H:%M:%S'), time_sub[0])
        )
    else:
        new_expire = dt.now() + timedelta(days=7)
        marzban_username = "user_" + str(user_id)
        conn.execute("""
            INSERT INTO subscriptions (user_id, vless_key, server_id, expires_at, plan_type, traffic_gb, marzban_username)
            VALUES (?,?,?,?,?,?,?)
        """, (user_id, "", 1, new_expire.strftime('%Y-%m-%d %H:%M:%S'), "time", 0, marzban_username))

    # 加20GB流量包
    traffic_sub = conn.execute(
        "SELECT id FROM subscriptions WHERE user_id=? AND plan_type='traffic'",
        (user_id,)
    ).fetchone()

    if traffic_sub:
        conn.execute(
            "UPDATE subscriptions SET traffic_gb = COALESCE(traffic_gb,0) + 20 WHERE id=?",
            (traffic_sub[0],)
        )
    else:
        expire_traffic = (dt.now() + timedelta(days=3650)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute("""
            INSERT INTO subscriptions (user_id, vless_key, server_id, expires_at, plan_type, traffic_gb, marzban_username)
            VALUES (?,?,?,?,?,?,?)
        """, (user_id, "", 2, expire_traffic, "traffic", 20, "user_" + str(user_id)))

    # 标记已领取
    conn.execute("""
        INSERT INTO user_sign_stats (user_id, total_consecutive, max_consecutive, monthly_gb, monthly_reset_date, last_sign_date, channel_joined, channel_reward_given)
        VALUES (?,0,0,0,NULL,NULL,1,1)
        ON CONFLICT(user_id) DO UPDATE SET channel_joined=1, channel_reward_given=1
    """, (user_id,))

    conn.commit()
    conn.close()

    # 同步 +7天 +20GB 到 PasarGuard(用 SQLite 真实 username)
    try:
        import asyncio as _asyncio
        import sqlite3 as _sql3
        from src.services.marzban_api import api as _api
        _conn2 = _sql3.connect("/opt/pg-shop/shop.db")
        _row = _conn2.execute(
            "SELECT marzban_username FROM subscriptions WHERE user_id=? AND marzban_username != '' ORDER BY id DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        _conn2.close()
        _mz_username = _row[0] if (_row and _row[0]) else ("user_" + str(user_id))
        _loop = _asyncio.get_event_loop()
        _loop.create_task(_api.add_expire_days(_mz_username, 7))
        _loop.create_task(_api.add_data_limit_gb(_mz_username, 20))
        logger.info(f"📊 入群 +7天+20GB 已同步到 PasarGuard: {_mz_username}")
    except Exception as _e:
        logger.error(f"入群同步 PasarGuard 失败: {_e}")

    builder = InlineKeyboardBuilder()
    builder.button(text="📦 查看我的订阅", callback_data="back_to_profile")
    builder.adjust(1)

    await callback.message.edit_text(
        "🎉 <b>领取成功！</b>\n\n"
        "━━━━━━━━━━━━\n\n"
        "✅ 已发放：\n"
        "  • <b>+7天</b> 订阅时间\n"
        "  • <b>+20GB</b> 流量包\n\n"
        "━━━━━━━━━━━━\n\n"
        "感谢加入 @DCxxeo 🎊",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "share_reward")
async def share_reward(callback: CallbackQuery, t=None, lang=None):
    print("🔔 share_reward 触发！user_id:", callback.from_user.id)
    from loguru import logger
    logger.info("share_reward 触发 user=" + str(callback.from_user.id))
    from datetime import date
    user_id = callback.from_user.id
    conn = get_db()
    today = date.today().isoformat()

    # 确保字段存在
    try:
        conn.execute("ALTER TABLE user_sign_stats ADD COLUMN share_count INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE user_sign_stats ADD COLUMN share_date DATE")
        conn.commit()
    except:
        pass

    # 确保用户有统计记录
    conn.execute("""
        INSERT OR IGNORE INTO user_sign_stats 
        (user_id, total_consecutive, max_consecutive, monthly_gb, channel_joined, channel_reward_given, share_count)
        VALUES (?,0,0,0,0,0,0)
    """, (user_id,))
    conn.commit()

    row = conn.execute(
        "SELECT share_count, share_date FROM user_sign_stats WHERE user_id=?",
        (user_id,)
    ).fetchone()

    share_count = row[0] if row and row[0] else 0
    share_date = row[1] if row else None

    if share_date != today:
        share_count = 0
        conn.execute(
            "UPDATE user_sign_stats SET share_count=0, share_date=? WHERE user_id=?",
            (today, user_id)
        )
        conn.commit()

    if share_count >= 2:
        conn.close()
        await callback.answer("❌ 今日分享奖励已领取(每天最多2次)", show_alert=True)
        return

    # 给用户加 1GB 流量到 subscriptions(全球通组 server_id=2)
    from datetime import datetime as _dt, timedelta as _td
    marzban_username = "user_" + str(user_id)
    traffic_sub = conn.execute(
        "SELECT id, traffic_gb FROM subscriptions WHERE user_id=? AND plan_type='traffic'",
        (user_id,)
    ).fetchone()
    if traffic_sub:
        conn.execute(
            "UPDATE subscriptions SET traffic_gb = COALESCE(traffic_gb,0) + 1 WHERE id=?",
            (traffic_sub[0],)
        )
    else:
        expire = (_dt.now() + _td(days=3650)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute("""
            INSERT INTO subscriptions (user_id, vless_key, server_id, expires_at, plan_type, traffic_gb, marzban_username)
            VALUES (?,?,?,?,?,?,?)
        """, (user_id, "", 2, expire, "traffic", 1, marzban_username))
    conn.execute(
        "UPDATE user_sign_stats SET share_count=?, share_date=? WHERE user_id=?",
        (share_count + 1, today, user_id)
    )
    conn.commit()

    # 同步 +1GB 到 PasarGuard(用 SQLite 真实 marzban_username)
    _share_mz_user = None
    try:
        _row = conn.execute(
            "SELECT marzban_username FROM subscriptions WHERE user_id=? AND marzban_username != '' ORDER BY id DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        if _row and _row[0]:
            _share_mz_user = _row[0]
    except Exception:
        pass

    new_balance = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()

    # 在 db 关闭后再做 PasarGuard 同步
    if _share_mz_user:
        try:
            import asyncio as _asyncio
            from src.services.marzban_api import api as _api
            _loop = _asyncio.get_event_loop()
            _loop.create_task(_api.add_data_limit_gb(_share_mz_user, 1))
            logger.info(f"📊 分享 +1GB 已同步到 PasarGuard: {_share_mz_user}")
        except Exception as _e:
            logger.error(f"分享同步 PasarGuard 失败: {_e}")

    balance = new_balance[0] if new_balance else 0
    remaining = 3 - share_count - 1

    await callback.answer(
        "✅ 分享奖励 +1GB 已到账！每天最多2次",
        show_alert=True
    )
