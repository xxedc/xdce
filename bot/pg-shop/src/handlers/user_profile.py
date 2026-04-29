from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from datetime import datetime
from src.utils.translations import get_text
from src.database.requests import get_user_subscriptions, get_user, async_session
from src.keyboards.builders import profile_kb, top_up_kb, payment_method_kb
from src.services.marzban_api import api
from sqlalchemy import select

router = Router()


async def get_profile_text(user_id: int, t, lang: str):
    """新版美化卡片"""
    user = await get_user(user_id)
    subs = await get_user_subscriptions(user_id)

    balance = user.balance if user else 0
    now = datetime.now()

    # ============ 头部 ============
    text = "👤 <b>我的账户</b>\n\n"
    text += f"🆔 <code>{user_id}</code>  ｜  💰 <b>{balance}¥</b>\n\n"

    if not subs:
        text += "━━━━━━━━━━━━━━\n\n"
        text += "📦 暂无订阅,点击下方开通\n"
        return text, profile_kb(lang, has_active_sub=False)

    # 找最佳订阅
    active = [s for s in subs if s.expires_at > now]
    time_subs = sorted(
        [s for s in active if getattr(s, 'plan_type', 'time') != 'traffic'],
        key=lambda s: s.expires_at, reverse=True
    )
    traffic_subs = sorted(
        [s for s in active if getattr(s, 'plan_type', 'time') == 'traffic'],
        key=lambda s: s.expires_at, reverse=True
    )
    best_time = time_subs[0] if time_subs else None
    best_traffic = traffic_subs[0] if traffic_subs else None
    best = best_time or best_traffic

    if not best:
        text += "📦 暂无活跃订阅\n"
        return text, profile_kb(lang, has_active_sub=False)

    # ============ 节点信息 ============
    text += "━━━━━━━━━━━━━━\n"
    text += "🌍 <b>全球通 Pro</b>  🟢\n"
    text += "⚡ 全节点 ｜ 低延迟 ｜ 原生直连\n\n"

    # ============ 到期时间 ============
    if best_time:
        days_left = (best_time.expires_at - now).days
        if days_left >= 3640:
            text += "⏳ <b>永久有效</b>\n\n"
        else:
            exp_str = best_time.expires_at.strftime("%Y-%m-%d")
            text += f"⏳ 到期 <b>{days_left} 天</b>(<code>{exp_str}</code>)\n\n"
    else:
        text += "⏳ 仅流量包,无时间订阅\n\n"

    # ============ 流量信息 ============
    text += "━━━━━━━━━━━━━━\n"
    text += "📊 <b>流量</b>\n"

    # 从 PasarGuard 获取实时数据
    _used_gb = 0.0
    _limit_gb = 200.0 if best_time else 0.0
    try:
        import aiohttp as _ahttp
        _h = await api._headers()
        async with _ahttp.ClientSession() as _s:
            async with _s.get(api.host + "/api/user/" + best.marzban_username, headers=_h) as _r:
                if _r.status == 200:
                    _d = await _r.json()
                    _used_gb = round((_d.get("used_traffic") or 0) / 1024**3, 2)
                    _limit_gb = round((_d.get("data_limit") or 0) / 1024**3, 1)
    except Exception:
        pass

    if best_time:
        text += f"   📡 <b>{_limit_gb:.0f}GB</b> / 月 · 已用 <b>{_used_gb}GB</b>\n"
    else:
        text += f"   📊 已用 <b>{_used_gb}GB</b>\n"

    if best_traffic:
        tgb = getattr(best_traffic, 'traffic_gb', 0) or 0
        if tgb > 0:
            text += f"   🎁 流量包 <b>+{tgb}GB</b>\n"
    text += "\n"

    # ============ 订阅链接 ============
    sub_url = ""
    for s in (time_subs + traffic_subs):
        if hasattr(s, "subscription_url") and s.subscription_url:
            sub_url = s.subscription_url
            break
    if sub_url:
        text += "━━━━━━━━━━━━━━\n"
        text += "🔗 <b>订阅链接</b>\n"
        text += f"<code>{sub_url}</code>\n"

    has_active = any(s.expires_at > now and getattr(s,'plan_type','time') != 'traffic' for s in subs)
    return text, profile_kb(lang, has_active_sub=has_active)


@router.message(F.text.in_(["📦 我的订阅", get_text("ru", "profile_btn")]))
async def profile(message: Message, t, lang):
    text, kb = await get_profile_text(message.from_user.id, t, lang)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: CallbackQuery, t, lang):
    text, kb = await get_profile_text(callback.from_user.id, t, lang)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()
