from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from datetime import datetime, timedelta
from loguru import logger

from src.keyboards.builders import location_kb, buy_type_kb, duration_kb, instruction_links_kb, payment_method_kb
from src.keyboards.reply import get_main_kb
from src.utils.translations import get_text
from src.services.marzban_api import api
from src.database.requests import add_subscription, get_user, set_trial_used, async_session, get_user_subscriptions
from sqlalchemy import select

router = Router()


async def get_usdt_rate() -> float:
    """获取实时 USD/CNY 汇率"""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://open.er-api.com/v6/latest/USD",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return round(float(data["rates"]["CNY"]), 2)
    except Exception:
        pass
    return 7.2

@router.message(F.text.in_(["🚀 开通订阅"]))
async def start_buy(message: Message, t, lang, state=None):
    if state: await state.clear()
    # 直接跳到套餐时长选择（默认全球通）
    from src.keyboards.builders import duration_kb
    user = await get_user(message.from_user.id)
    balance = user.balance if user else 0
    rate = await get_usdt_rate()
    # 根据实时汇率计算各套餐USDT价格
    def to_usdt(cny): return round(cny / rate, 2)

    text = (
        "╔══════════════════╗\n"
        "      🛒 开通订阅\n"
        "╚══════════════════╝\n\n"
        "💰 余额：<b>" + str(balance) + "¥</b>   💱 实时汇率 <b>1 USDT ≈ " + str(rate) + "¥</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🌍 <b>全球通 · 全节点接入</b>\n\n"
        "📶 <b>支持协议</b>\n"
        "🔐 VLESS Reality  ← 推荐，最强抗封锁\n"
        "🌐 VLESS / VMess  WS · gRPC · HTTP\n"
        "🛡 Trojan         TCP · WS · gRPC\n"
        "⚡️ Shadowsocks    高速稳定\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ iOS · Android · Windows · Mac\n"
        "✅ 每台设备均可用 · 不限速\n"
        "✅ 自动切换最优线路\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>选择时长，立即开通</b>"
    )
    await message.answer(text, reply_markup=duration_kb(lang, "multi"), parse_mode="HTML")

@router.message(F.text.in_(["🎁 免费试用"]))
async def get_trial(message: Message, t, lang):
    user_id = message.from_user.id
    
    # 1. Проверяем, брал ли уже
    user = await get_user(user_id)
    if user and user.is_trial_used:
        await message.answer(t("trial_used"), parse_mode="HTML")
        return

    # 直接激活试用，默认全球通节点
    await message.answer(t("gen_key"), parse_mode="HTML")
    
    class FakeCallback:
        class data:
            pass
        class message:
            pass
        class from_user:
            pass
    
    # 模拟选择 multi 节点
    class MockCallback:
        data = "trial_multi"
        from_user = message.from_user
        class message_obj:
            pass
    
    # 直接调用试用逻辑
    import types
    mock = types.SimpleNamespace(
        data="trial_multi",
        from_user=message.from_user,
        message=types.SimpleNamespace(
            edit_text=message.answer,
            delete=lambda: None,
            answer=message.answer
        ),
        answer=message.answer
    )
    await _process_trial("multi", message.from_user.id, message, t, lang)



async def _process_trial(location_code: str, user_id: int, message_obj, t, lang):
    """处理试用激活逻辑"""
    from datetime import datetime, timedelta
    
    try:
        username = f"trial_{user_id}"
        expire_date = datetime.now() + timedelta(days=7)
        expire_ts = int(expire_date.timestamp())

        key, sub_url = await api.create_key(
            username=username,
            expire_timestamp=expire_ts,
            data_limit_gb=30
        )

        await add_subscription(
            tg_id=user_id,
            key_data=key,
            server_code=location_code,
            expires_at=expire_date,
            device_limit=1,
            marzban_username=username,
            subscription_url=sub_url,
            plan_type="time",
            traffic_gb=30
        )

        await set_trial_used(user_id)

        date_str = expire_date.strftime('%Y-%m-%d %H:%M')
        days_left = (expire_date - datetime.now()).days
        hours_left = ((expire_date - datetime.now()).seconds) // 3600
        remaining = str(days_left) + "天 " + str(hours_left) + "小时"

        if sub_url:
            msg = (
                "<b>🎁 试用已激活！</b>\n\n"
                "📡 节点：🌍 全球通\n"
                "⏳ 有效期：7天 / 30GB\n"
                "⏳ 到期时间：" + date_str + "\n"
                "⏱ 剩余时间：" + remaining + "\n\n"
                "📋 <b>订阅链接：</b>\n"
                "<code>" + sub_url + "</code>"
            )
        else:
            msg = (
                "<b>🎁 试用已激活！</b>\n\n"
                "⏳ 到期时间：" + date_str + "\n"
                "<code>" + key + "</code>"
            )

        await message_obj.answer(msg, parse_mode="HTML")
        await message_obj.answer(
            t("choose_action"),
            reply_markup=get_main_kb(lang, is_trial_used=True)
        )
    except Exception as e:
        logger.error(f"❌ 试用激活失败 {user_id}: {e}")
        await message_obj.answer(t("error"), parse_mode="HTML")

@router.callback_query(F.data.startswith("trial_"))
async def process_trial_selection(callback: CallbackQuery, t, lang):
    user_id = callback.from_user.id
    location_code = callback.data.split("_")[1]
    
    # Повторная проверка (на случай если кликнул дважды)
    user = await get_user(user_id)
    if user and user.is_trial_used:
        await callback.message.edit_text(t("trial_used"), parse_mode="HTML")
        return

    await callback.message.edit_text(t("gen_key"))

    try:
        # Генерируем ключ для ТЕСТА (Лимит 1 устройство)
        # Временно убираем limit=1 из вызова API, так как метод его не поддерживает
        username = f"trial_{user_id}"
        expire_date = datetime.now() + timedelta(days=7)  # 7天试用
        expire_ts = int(expire_date.timestamp())

        # 同步到 Marzban：7天有效期，30GB流量不重置
        key, sub_url = await api.create_key(
            username=username,
            expire_timestamp=expire_ts,
            data_limit_gb=30
        )

        await add_subscription(
            tg_id=user_id,
            key_data=key,
            server_code=location_code,
            expires_at=expire_date,
            device_limit=1,
            marzban_username=username,
            subscription_url=sub_url,
            plan_type="time",
            traffic_gb=30
        )
        
        # Отмечаем, что триал использован
        await set_trial_used(user_id)
        
        # Форматируем время для ответа
        date_str = expire_date.strftime('%Y-%m-%d %H:%M')
        # Для триала всегда < 1 дня, поэтому показываем часы и минуты
        if lang == "ru":
            remaining = "6天 23小时"  # 7天试用
        else:
            remaining = "6天 23小时"  # 7天试用
            
        location_name = t("swe") if location_code == "swe" else t("ger")
        
        logger.success(f"🎁 Выдан Trial юзеру {user_id} ({location_code})")
        
        # Удаляем сообщение с кнопками и отправляем новое с обновленной клавиатурой (без кнопки теста)
        await callback.message.delete()
        days_left_trial = (expire_date - datetime.now()).days
        hours_left_trial = ((expire_date - datetime.now()).seconds) // 3600
        remaining_trial = str(days_left_trial) + "天 " + str(hours_left_trial) + "小时"

        if sub_url:
            trial_msg = (
                "<b>🎁 试用已激活！</b>\n\n"
                "📡 节点：" + location_name + "\n"
                "⏳ 有效期：7天 / 30GB\n"
                "⏳ 到期时间：" + date_str + "\n"
                "⏱ 剩余时间：" + remaining_trial + "\n\n"
                "📋 <b>订阅链接（复制到客户端导入）：</b>\n"
                "<code>" + sub_url + "</code>"
            )
        else:
            trial_msg = (
                "<b>🎁 试用已激活！</b>\n\n"
                "📡 节点：" + location_name + "\n"
                "⏳ 有效期：7天 / 30GB\n"
                "⏳ 到期时间：" + date_str + "\n"
                "<code>" + key + "</code>"
            )
        await callback.message.answer(trial_msg, parse_mode="HTML", reply_markup=instruction_links_kb().as_markup())

        # Обновляем главное меню (убираем кнопку теста)
        await callback.message.answer(
            t("choose_action"),
            reply_markup=get_main_kb(lang, is_trial_used=True)
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка выдачи Trial {user_id}: {e}")
        await callback.message.edit_text(t("error"), parse_mode="HTML")

@router.callback_query(F.data == "type_single")
async def select_single_location(callback: CallbackQuery, t, lang):
    # Шаг 2 (ветка Соло): Показываем список стран
    await callback.message.edit_text(t("choose_location"), reply_markup=location_kb(lang))

@router.callback_query(F.data == "back_to_types")
async def back_to_main_buy_menu(callback: CallbackQuery, t, lang):
    from src.keyboards.builders import duration_kb
    user = await get_user(callback.from_user.id)
    balance = user.balance if user else 0
    rate = await get_usdt_rate()
    text = (
        "╔══════════════════╗\n"
        "      🚀 开通订阅\n"
        "╚══════════════════╝\n\n"
        "💰 余额：<b>" + str(balance) + "¥</b>   💱 实时汇率 <b>1 USDT ≈ " + str(rate) + "¥</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>套餐包含</b>\n\n"
        "✅ 全球所有节点无限切换\n"
        "✅ 同时支持 5 台设备\n"
        "✅ 每月 200GB（时间套餐）\n"
        "✅ 不限速 · 稳定可靠\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📶 <b>支持全部主流协议</b>\n\n"
        "🔐 VLESS Reality   最强抗封锁\n"
        "🌐 VLESS / VMess   WS · gRPC\n"
        "🛡 Trojan          TCP · WS\n"
        "⚡ Shadowsocks     高速备用\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>选择套餐时长</b>"
    )
    await callback.message.edit_text(text, reply_markup=duration_kb(lang, "multi", rate=rate), parse_mode="HTML")
    await callback.answer()
    
@router.callback_query(F.data.startswith("buy_"))
async def select_duration(callback: CallbackQuery, t, lang):
    location_code = callback.data.split("_")[1]
    rate = await get_usdt_rate()
    user = await get_user(callback.from_user.id)
    balance = user.balance if user else 0

    text = (
        "╔══════════════════╗\n"
        "      🚀 开通订阅\n"
        "╚══════════════════╝\n\n"
        "💰 余额：<b>" + str(balance) + "¥</b>   💱 实时汇率 <b>1 USDT ≈ " + str(rate) + "¥</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>套餐包含</b>\n\n"
        "✅ 全球所有节点无限切换\n"
        "✅ 同时支持 5 台设备\n"
        "✅ 每月 200GB（时间套餐）\n"
        "✅ 不限速 · 稳定可靠\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📶 <b>支持全部主流协议</b>\n\n"
        "🔐 VLESS Reality   最强抗封锁\n"
        "🌐 VLESS / VMess   WS · gRPC\n"
        "🛡 Trojan          TCP · WS\n"
        "⚡ Shadowsocks     高速备用\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>选择套餐时长</b>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=duration_kb(lang, location_code, rate=rate),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("prepay_"))
async def show_payment_methods(callback: CallbackQuery, t, lang):
    # Формат data: prepay_{location}_{days}_{price}
    _, location_code, days_str, price_str = callback.data.split("_")
    days = int(days_str)
    price = int(price_str)
    
    user_id = callback.from_user.id
    user = await get_user(user_id)
    balance = user.balance if user else 0
    
    # 获取实时汇率
    rate = await get_usdt_rate()
    usdt = round(price / rate, 2)

    # 套餐名称
    days_label = {30: "1个月", 90: "3个月", 180: "6个月", 365: "12个月", 0: "流量包500GB"}
    plan_name = days_label.get(days, str(days) + "天")

    text = (
        "💳 <b>选择支付方式</b>\n\n"
        "📦 套餐：<b>" + plan_name + "</b>\n"
        "💰 价格：<b>" + str(price) + "¥ / " + str(usdt) + " USDT</b>\n"
        "💱 实时汇率：<b>1 USDT ≈ " + str(rate) + "¥</b>\n\n"
        "账户余额：<b>" + str(balance) + "¥</b>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=payment_method_kb(lang, balance, price, location_code, days),
        parse_mode="HTML"
    )

async def issue_key(user_id: int, username: str, location_code: str, days: int, t, lang, message: Message, price: int = 0):
    """Вспомогательная функция для выдачи ключа после успешной оплаты"""
    
    # Логируем действие!
    logger.info(f"💰 Юзер {user_id} получает ключ: {location_code} на {days} дней")

    # 统一使用全球通节点
    location_name = "🌍 全球通（所有节点）"
    device_limit = 5
    
    await message.edit_text(t("gen_key"))
    
    try:
        # Генерируем ключ с учетом лимита устройств
        # Временно убираем limit из вызова API
        username = f"user_{user_id}"
        trial_username = f"trial_{user_id}"

        # ==================================================
        # 试用 → 永久号 自动升级逻辑
        # ==================================================
        is_first_upgrade = False
        accumulated_gb = 0  # 累积的奖励流量(从 SQLite traffic_gb 字段汇总)
        try:
            import sqlite3 as _sql3
            _c = _sql3.connect("/opt/pg-shop/shop.db")

            # 检查是否有 user_xxx 已存在(用直接 GET,更可靠)
            _has_user_account = False
            try:
                import aiohttp as _aio_chk
                _h_chk = await api._headers()
                async with _aio_chk.ClientSession() as _s_chk:
                    async with _s_chk.get(api.host + "/api/user/" + username, headers=_h_chk) as _r_chk:
                        if _r_chk.status == 200:
                            _has_user_account = True
            except Exception:
                pass

            if not _has_user_account:
                is_first_upgrade = True
                logger.info(f"🎓 用户 {user_id} 首次升级到永久账号")

                # 1a. 累计 SQLite 里所有 traffic 行的 traffic_gb(签到/分享/入群奖励流量)
                _row = _c.execute(
                    "SELECT COALESCE(SUM(traffic_gb), 0) FROM subscriptions WHERE user_id=? AND plan_type='traffic'",
                    (user_id,)
                ).fetchone()
                accumulated_gb = int(_row[0] or 0) if _row else 0

                # 1a2. 加上试用账号未用完的流量(30GB - 已用)
                try:
                    import aiohttp as _aio_h
                    _h = await api._headers()
                    async with _aio_h.ClientSession() as _s:
                        async with _s.get(api.host + "/api/user/" + trial_username, headers=_h) as _r:
                            if _r.status == 200:
                                _td = await _r.json()
                                _trial_limit_gb = (_td.get("data_limit") or 0) / 1024**3
                                _trial_used_gb = (_td.get("used_traffic") or 0) / 1024**3
                                _trial_remaining = max(0, _trial_limit_gb - _trial_used_gb)
                                accumulated_gb += int(_trial_remaining)
                                logger.info(f"📦 试用剩余流量 {_trial_remaining:.1f}GB,加入累积")
                except Exception as _te:
                    logger.warning(f"读取试用剩余流量失败: {_te}")

                # 1b. 累计剩余天数(trial 到期 + 入群 +7 天)
                from datetime import datetime as _dt2
                _row_exp = _c.execute(
                    "SELECT MAX(expires_at) FROM subscriptions WHERE user_id=? AND plan_type='time' AND marzban_username LIKE 'trial_%'",
                    (user_id,)
                ).fetchone()
                accumulated_days = 0
                if _row_exp and _row_exp[0]:
                    try:
                        _trial_exp = _dt2.fromisoformat(_row_exp[0].split(".")[0])
                        _now = _dt2.now()
                        if _trial_exp > _now:
                            accumulated_days = (_trial_exp - _now).days
                    except Exception:
                        accumulated_days = 0
                logger.info(f"🎁 用户 {user_id} 累积奖励 {accumulated_gb}GB + {accumulated_days}天,将迁移到 user 账号")

                # 2. 删除 PasarGuard 后台的 trial_xxx
                try:
                    _ok = await api.delete_user(trial_username)
                    if _ok:
                        logger.info(f"🗑 已删除 PasarGuard trial 账号: {trial_username}")
                except Exception as _e:
                    logger.warning(f"删除 trial_xxx 失败(可能本来不存在): {_e}")

                # 3. SQLite 里把所有 trial_xxx 的 marzban_username 改成 user_xxx
                _c.execute(
                    "UPDATE subscriptions SET marzban_username=? WHERE user_id=? AND marzban_username LIKE 'trial_%'",
                    (username, user_id)
                )
                _c.commit()
                logger.info(f"🔄 SQLite 已把所有 trial_xxx 行改成 user_xxx")

            _c.close()
        except Exception as _ue:
            logger.error(f"升级逻辑失败(不阻塞购买): {_ue}")

        # 获取已有订阅，时间套餐叠加到期时间
        existing_subs = await get_user_subscriptions(user_id)
        now_dt = datetime.now()

        if days == 0:
            # 流量包：设置一个很远的日期，实际靠流量控制
            expire_date = datetime.now() + timedelta(days=3650)
            new_traffic = 500
        else:
            # 时间套餐：在已有时间套餐到期时间基础上叠加（不叠加流量包时间）
            existing_time = None
            for s in existing_subs:
                pt = getattr(s, 'plan_type', 'time')
                if pt == 'time' and s.expires_at > now_dt:
                    existing_time = s
                    break
            if existing_time:
                expire_date = existing_time.expires_at + timedelta(days=days)
            else:
                expire_date = now_dt + timedelta(days=days)
            new_traffic = 0

        # 同步到期时间和流量到 Marzban 面板
        import time as _time
        if days == 0:
            _expire_ts = 0        # 流量包不限时间
            _data_gb = 500        # 500GB每月重置
        else:
            _expire_ts = int(expire_date.timestamp())
            _data_gb = 200        # 时间套餐200GB每月重置

        key, sub_url = await api.create_key(
            username=username,
            expire_timestamp=_expire_ts,
            data_limit_gb=_data_gb
        )

        # 首次升级时,把累积的奖励流量和天数加到新创建的 user_xxx
        if is_first_upgrade:
            if accumulated_gb > 0:
                try:
                    ok = await api.add_data_limit_gb(username, accumulated_gb)
                    if ok:
                        logger.success(f"🎁 已迁移 {accumulated_gb}GB 累积奖励到 {username}")
                except Exception as _me:
                    logger.error(f"迁移奖励流量失败: {_me}")
            # 注意: 首次升级时, expire_date 已经包含 trial 剩余天数(因为 existing_time = trial 行)
            # 这里 add_expire_days 会重复加, 所以跳过
            logger.info(f"🎁 试用剩余 {accumulated_days} 天已通过 expire_date 计算包含, 不重复 add_expire_days")

        # 用 Marzban 返回的最新订阅链接(确保和面板一致)
        if sub_url:
            import aiohttp as _aio_sync
            try:
                _h_sync = await api._headers()
                async with _aio_sync.ClientSession() as _s_sync:
                    async with _s_sync.get(
                        api.host + "/api/user/" + username,
                        headers=_h_sync
                    ) as _r_sync:
                        if _r_sync.status == 200:
                            _d_sync = await _r_sync.json()
                            _latest = _d_sync.get("subscription_url", "")
                            if _latest:
                                if not _latest.startswith("http"):
                                    _latest = api.host + _latest
                                sub_url = _latest
            except Exception:
                pass

        await add_subscription(
            tg_id=user_id,
            key_data=key,
            server_code=location_code,
            expires_at=expire_date,
            device_limit=device_limit,
            marzban_username=username,
            subscription_url=sub_url,
            plan_type="traffic" if days == 0 else "time",
            traffic_gb=new_traffic
        )
        
        # 触发邀请返佣
        try:
            from src.database.requests import process_referral_reward
            reward = await process_referral_reward(user_id, price if "price" in dir() else 0)
            if reward:
                logger.info("💰 邀请返佣已发放")
        except Exception:
            pass

        # 记录消费账单
        try:
            from src.database.requests import add_billing_record
            plan_label = "流量包 500GB" if days == 0 else (str(days) + "天订阅")
            await add_billing_record(
                user_id,
                -price,
                "purchase",
                "购买" + plan_label + " - " + location_name
            )
        except Exception:
            pass

        # Логируем успех!
        logger.success(f"✅ Ключ выдан юзеру {user_id}")

        # 计算显示时间
        if days == 0:
            time_line = "⏳ 有效期：永久（无到期时间）"
        else:
            date_str = expire_date.strftime("%Y-%m-%d %H:%M")
            days_left = (expire_date - datetime.now()).days
            remaining = str(days_left) + "天"
            time_line = "⏳ 到期时间：" + date_str + "\n⏱ 剩余时间：" + remaining

        if sub_url:
            msg = (
                "✅ <b>购买成功！</b>\n\n"
                "📡 节点：" + location_name + "\n"
                + time_line + "\n\n"
                "📋 <b>订阅链接（支持全部协议，复制到客户端导入）：</b>\n"
                "<code>" + sub_url + "</code>"
            )
        else:
            msg = (
                "✅ <b>购买成功！</b>\n\n"
                "📡 节点：" + location_name + "\n"
                + time_line + "\n\n"
                "<code>" + key + "</code>"
            )
        await message.answer(msg, parse_mode="HTML", reply_markup=instruction_links_kb().as_markup())
    except Exception as e:
        logger.error(f"❌ Ошибка при выдаче ключа юзеру {user_id}: {e}")
        await message.edit_text(t("error"), parse_mode="HTML")

@router.callback_query(F.data.startswith("confirm_balance_"))
async def process_balance_pay(callback: CallbackQuery, t, lang):
    # confirm_balance_{location}_{days}_{price}
    _, _, location_code, days_str, price_str = callback.data.split("_")
    days = int(days_str)
    price = int(price_str)
    user_id = callback.from_user.id

    # Транзакция списания
    async with async_session() as session:
        from src.database.models import User
        user = await session.scalar(select(User).where(User.id == user_id))
        
        if user.balance < price:
            await callback.answer(t("insufficient_funds"), show_alert=True)
            return
        
        user.balance -= price
        await session.commit()
        logger.info(f"💸 Списано {price}р с баланса юзера {user_id}")

    # Выдаем ключ
    await issue_key(user_id, callback.from_user.username, location_code, days, t, lang, callback.message, price=price)

@router.callback_query(F.data.startswith("confirm_online_"))
async def process_online_pay(callback: CallbackQuery, t, lang):
    # confirm_online_{location}_{days}_{price}
    from src.services.payment import payment as crypto_payment
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    import uuid as _uuid

    parts = callback.data.split("_")
    location_code = parts[2]
    days = int(parts[3])
    price = int(parts[4])
    user_id = callback.from_user.id

    # CNY to USDT (1 USD ≈ 7.2 CNY, 1 USDT ≈ 1 USD)
    usdt_amount = round(price / 7.2, 2)
    order_id = _uuid.uuid4().hex[:16]

    await callback.answer("⏳ 正在生成支付订单...")

    try:
        result = await crypto_payment.create_invoice(
            amount=usdt_amount,
            currency="USD",
            order_id=order_id,
            user_id=user_id
        )

        if result.get("state") == 0:
            data = result.get("result", {})
            pay_url = str(data.get("url") or "")
            pay_amount = str(data.get("amount") or usdt_amount)
            uuid_val = str(data.get("uuid") or order_id)

            # 存储订单信息到数据库，付款后回调使用
            from src.database.core import async_session
            from src.database.models import User
            async with async_session() as session:
                user = await session.scalar(select(User).where(User.id == user_id))
                if user:
                    # 用 note 字段存储待支付订单信息
                    import json as _json
                    pending = _json.dumps({
                        "order_id": order_id,
                        "location": location_code,
                        "days": days,
                        "price": price
                    })
                    # 存入用户备注临时字段（用balance_pending标记）
                    pass
                await session.commit()

            builder = InlineKeyboardBuilder()
            if pay_url:
                builder.button(text="💳 点击支付", url=pay_url)
            builder.button(
                text="✅ 我已付款，确认到账",
                callback_data="buy_paid_" + order_id[:12] + "_" + location_code + "_" + str(days) + "_" + str(price)
            )
            builder.button(text="🔙 取消", callback_data="back_to_profile")
            builder.adjust(1)

            text = (
                "💳 <b>在线支付</b>\n\n"
                "套餐金额：<b>" + str(price) + "¥</b>\n"
                "应付：<b>" + pay_amount + " USDT</b>\n\n"
                "点击「点击支付」完成付款\n"
                "付款后点击「我已付款」确认\n\n"
                "⏰ 有效期：60分钟"
            )
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        else:
            err = str(result.get("message") or "未知错误")
            await callback.message.edit_text(
                "❌ 创建订单失败：" + err,
                reply_markup=InlineKeyboardBuilder().button(text="🔙 返回", callback_data="back_to_profile").as_markup()
            )
    except Exception as e:
        await callback.message.edit_text(
            "❌ 支付系统错误：" + str(e),
            reply_markup=InlineKeyboardBuilder().button(text="🔙 返回", callback_data="back_to_profile").as_markup()
        )


@router.callback_query(F.data.startswith("buy_paid_"))
async def confirm_buy_paid(callback: CallbackQuery, t, lang):
    """用户点击已付款后，验证支付状态并发放订阅"""
    from src.services.payment import payment as crypto_payment
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    parts = callback.data.split("_")
    order_id = parts[2]
    location_code = parts[3]
    days = int(parts[4])
    price = int(parts[5])
    user_id = callback.from_user.id

    await callback.answer("⏳ 验证支付中...")

    try:
        result = await crypto_payment.check_payment(order_id)
        data = result.get("result", {})
        status = data.get("payment_status") or data.get("status") or ""

        if status in ("paid", "paid_over", "wrong_amount_waiting", "check"):
            # 支付成功或待确认，直接发放订阅
            await issue_key(user_id, callback.from_user.username, location_code, days, t, lang, callback.message, price=price)
        else:
            builder = InlineKeyboardBuilder()
            builder.button(text="🔄 再次确认", callback_data=callback.data)
            builder.button(text="🔙 取消", callback_data="back_to_profile")
            builder.adjust(1)
            await callback.message.edit_text(
                "⏳ <b>未检测到付款</b>\n\n"
                "状态：" + str(status) + "\n\n"
                "请确认已完成付款后再点击确认",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
    except Exception as e:
        await callback.answer("验证失败：" + str(e), show_alert=True)