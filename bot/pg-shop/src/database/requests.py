from datetime import datetime, timedelta
from src.database.core import async_session
from src.database.models import User, Subscription, Server, PromoCode, PromoUsage
from sqlalchemy import select, func, delete
from sqlalchemy.orm import joinedload

async def add_user(tg_id: int, username: str, lang_code: str = "en"):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.id == tg_id))
        if not user:
            session.add(User(id=tg_id, username=username, language_code=lang_code))
            await session.commit()

async def update_user_language(tg_id: int, lang_code: str):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.id == tg_id))
        if user:
            user.language_code = lang_code
            await session.commit()

async def set_trial_used(tg_id: int):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.id == tg_id))
        if user:
            user.is_trial_used = True
            await session.commit()

async def get_user(tg_id: int):
    async with async_session() as session:
        return await session.scalar(select(User).where(User.id == tg_id))

async def get_user_by_username(username: str):
    async with async_session() as session:
        # Убираем @ если есть и ищем без учета регистра (если база позволяет, иначе exact match)
        clean_username = username.lstrip("@")
        return await session.scalar(select(User).where(User.username == clean_username))

async def get_all_users_ids():
    async with async_session() as session:
        return (await session.scalars(select(User.id))).all()

async def add_subscription(tg_id: int, key_data: str, server_code: str, expires_at, device_limit: int = 0, marzban_username: str = None, subscription_url: str = None, plan_type: str = "time", traffic_gb: int = 0):
    async with async_session() as session:
        server = await session.scalar(select(Server).where(Server.name == server_code))
        if not server:
            server = Server(name=server_code, ip_address="127.0.0.1", location=server_code.upper())
            session.add(server)
            await session.flush()

        if plan_type == "traffic":
            # 流量包：找已有流量包记录累加，没有则新建
            existing = await session.scalar(
                select(Subscription).where(
                    Subscription.user_id == tg_id,
                    Subscription.plan_type == "traffic"
                )
            )
            if existing:
                existing.traffic_gb = (existing.traffic_gb or 0) + traffic_gb
                existing.marzban_username = marzban_username
                if subscription_url:
                    existing.subscription_url = subscription_url
            else:
                session.add(Subscription(
                    user_id=tg_id,
                    vless_key=key_data,
                    server_id=server.id,
                    expires_at=expires_at,
                    device_limit=device_limit,
                    marzban_username=marzban_username,
                    subscription_url=subscription_url,
                    plan_type="traffic",
                    traffic_gb=traffic_gb
                ))
        else:
            # 时间套餐：找已有时间套餐记录更新到期时间，没有则新建
            existing = await session.scalar(
                select(Subscription).where(
                    Subscription.user_id == tg_id,
                    Subscription.plan_type == "time"
                )
            )
            if existing:
                existing.vless_key = key_data
                existing.server_id = server.id
                existing.expires_at = expires_at
                existing.device_limit = device_limit
                existing.marzban_username = marzban_username
                if subscription_url:
                    existing.subscription_url = subscription_url
                existing.status = "active"
            else:
                session.add(Subscription(
                    user_id=tg_id,
                    vless_key=key_data,
                    server_id=server.id,
                    expires_at=expires_at,
                    device_limit=device_limit,
                    marzban_username=marzban_username,
                    subscription_url=subscription_url,
                    plan_type="time",
                    traffic_gb=traffic_gb
                ))
        await session.commit()

async def get_user_subscriptions(tg_id: int):
    async with async_session() as session:
        result = await session.scalars(
            select(Subscription)
            .where(Subscription.user_id == tg_id)
            .options(joinedload(Subscription.server))
        )
        return result.all()

async def get_stats():
    async with async_session() as session:
        # Всего пользователей
        total_users = await session.scalar(select(func.count(User.id)))
        
        # Активные подписки (где статус active и дата окончания в будущем)
        # Примечание: тут упрощенная проверка, в идеале проверять дату > now()
        active_subs = await session.scalar(select(func.count(Subscription.id)).where(Subscription.status == 'active'))
        
        return total_users, active_subs

async def get_promo(code_text: str):
    async with async_session() as session:
        return await session.scalar(select(PromoCode).where(PromoCode.code == code_text, PromoCode.is_active == True))

async def is_promo_used_by_user(tg_id: int, promo_id: int) -> bool:
    async with async_session() as session:
        usage = await session.scalar(select(PromoUsage).where(
            PromoUsage.user_id == tg_id, 
            PromoUsage.promo_id == promo_id
        ))
        return usage is not None

async def activate_promo(tg_id: int, code_text: str, key_data: str = None, marzban_username: str = None, subscription_id: int = None):
    """
    Проверяет и активирует промокод.
    Возвращает кортеж (успех: bool, сообщение: str, тип: str, значение: int, extra_data: dict)
    """
    async with async_session() as session:
        # 1. Ищем код
        promo = await session.scalar(select(PromoCode).where(PromoCode.code == code_text, PromoCode.is_active == True))
        
        if not promo:
            return False, "not_found", None, 0, None
            
        # 2. Проверки валидности
        if promo.expires_at and promo.expires_at < datetime.now():
            return False, "expired", None, 0, None
            
        if promo.max_uses > 0 and promo.current_uses >= promo.max_uses:
            return False, "limit_reached", None, 0, None
            
        # 3. Проверка на повторное использование
        usage = await session.scalar(select(PromoUsage).where(
            PromoUsage.user_id == tg_id, 
            PromoUsage.promo_id == promo.id
        ))
        if usage:
            return False, "already_used", None, 0, None
            
        # 4. Активация
        user = await session.scalar(select(User).where(User.id == tg_id))
        
        if promo.type == 'balance':
            user.balance += promo.value
        elif promo.type == 'days':
            # Продлеваем последнюю активную подписку или все (тут логика для последней)
            # В реальном проекте лучше уточнять какую продлевать, но для простоты берем последнюю
            if subscription_id:
                sub = await session.scalar(select(Subscription).where(Subscription.id == subscription_id, Subscription.user_id == tg_id))
            else:
                # 只取时间套餐，不取流量包
                sub = await session.scalar(
                    select(Subscription).where(
                        Subscription.user_id == tg_id,
                        Subscription.plan_type == 'time'
                    ).order_by(Subscription.expires_at.desc()).limit(1)
                )
            
            if sub:
                # Если подписка уже истекла, добавляем дни к текущему моменту (чтобы сразу заработала)
                # Если активна — добавляем к дате окончания
                if sub.expires_at < datetime.now():
                    sub.expires_at = datetime.now() + timedelta(days=promo.value)
                else:
                    sub.expires_at += timedelta(days=promo.value)

                # 同步到 Marzban
                try:
                    from src.services.marzban_api import api as _mapi
                    import aiohttp as _ahttp
                    _expire_ts = int(sub.expires_at.timestamp())
                    _username = sub.marzban_username
                    _is_trial = _username.startswith("trial_") if _username else False
                    _monthly_gb = 30 if _is_trial else 200
                    _payload = {
                        "expire": _expire_ts,
                        "data_limit": int(_monthly_gb * 1024**3),
                        "data_limit_reset_strategy": "month",
                        "status": "active"
                    }
                    _headers = await _mapi._headers()
                    async with _ahttp.ClientSession() as _sess:
                        await _sess.put(
                            _mapi.host + "/api/user/" + _username,
                            json=_payload,
                            headers=_headers
                        )
                except Exception:
                    pass
                
                # Если статус был expired/banned, возвращаем active
                if sub.status != 'active':
                    sub.status = 'active'
            else:
                return False, "no_sub_to_extend", None, 0, None
        elif promo.type == 'subscription':
            if not key_data:
                return False, "error", None, 0, None
            
            extra = promo.extra_data or {}
            days = extra.get('days', 30)
            limit = extra.get('limit', 1)
            location_code = extra.get('location', 'multi')
            
            server = await session.scalar(select(Server).where(Server.name == location_code))
            if not server:
                server = Server(name=location_code, ip_address="127.0.0.1", location=location_code.upper())
                session.add(server)
                await session.flush()

            sub = Subscription(
                user_id=tg_id,
                vless_key=key_data,
                server_id=server.id,
                expires_at=datetime.now() + timedelta(days=days),
                device_limit=limit,
                marzban_username=marzban_username
            )
            session.add(sub)

        promo.current_uses += 1
        session.add(PromoUsage(user_id=tg_id, promo_id=promo.id))
        await session.commit()
        
        return True, "success", promo.type, promo.value, promo.extra_data

async def create_promo_code(code: str, type: str, value: int, max_uses: int = 0):
    async with async_session() as session:
        existing = await session.scalar(select(PromoCode).where(PromoCode.code == code))
        if existing:
            return False
        
        promo = PromoCode(code=code, type=type, value=value, max_uses=max_uses)
        session.add(promo)
        await session.commit()
        return True

async def get_all_promos():
    async with async_session() as session:
        # Показываем только активные промокоды
        return (await session.scalars(select(PromoCode).where(PromoCode.is_active == True).order_by(PromoCode.id.desc()))).all()

async def get_promo_by_id(promo_id: int):
    async with async_session() as session:
        return await session.scalar(select(PromoCode).where(PromoCode.id == promo_id))

async def delete_promo(promo_id: int):
    async with async_session() as session:
        promo = await session.scalar(select(PromoCode).where(PromoCode.id == promo_id))
        if not promo:
            return False

        # Проверяем, использовался ли промокод
        usage_count = await session.scalar(select(func.count(PromoUsage.id)).where(PromoUsage.promo_id == promo_id))

        if usage_count == 0:
            # Если промокод ни разу не использовали, можно удалить физически (чисто и безопасно)
            await session.delete(promo)
        else:
            # Если история есть — делаем Soft Delete
            promo.is_active = False
            # Переименовываем, чтобы освободить красивое имя (например: SALE -> SALE_del_17123456)
            promo.code = f"{promo.code}_del_{int(datetime.now().timestamp())}"
        
        await session.commit()
        return True

async def update_user_balance(user_id: int, amount: int):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        if user:
            user.balance += amount
            await session.commit()

async def set_referrer(tg_id: int, referrer_id: int):
    """设置邀请人（只在用户第一次注册时设置）"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.id == tg_id))
        if user and not user.referrer_id and user.id != referrer_id:
            user.referrer_id = referrer_id
            await session.commit()
            return True
    return False

async def process_referral_reward(buyer_id: int, purchase_amount: int):
    """购买成功后给邀请人发放奖励"""
    from datetime import datetime, timedelta
    async with async_session() as session:
        buyer = await session.scalar(select(User).where(User.id == buyer_id))
        if not buyer or not buyer.referrer_id:
            return False

        # 检查是否是首次购买（referral_count用来判断邀请人是否已获过这个买家的奖励）
        # 用 referral_earnings 字段记录
        referrer = await session.scalar(select(User).where(User.id == buyer.referrer_id))
        if not referrer:
            return False

        # 计算返佣金额（10%）
        reward_balance = int(purchase_amount * 0.1)

        # 给邀请人加余额
        referrer.balance += reward_balance
        referrer.referral_earnings += reward_balance
        referrer.referral_count += 1

        # 给邀请人延长订阅7天
        sub = await session.scalar(
            select(Subscription).where(
                Subscription.user_id == referrer.id,
                Subscription.plan_type == "time"
            )
        )
        if sub:
            if sub.expires_at > datetime.now():
                sub.expires_at = sub.expires_at + timedelta(days=7)
            else:
                sub.expires_at = datetime.now() + timedelta(days=7)

        await session.commit()
        return reward_balance

async def get_referral_stats(tg_id: int):
    """获取用户邀请统计"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.id == tg_id))
        if not user:
            return None
        return {
            "count": user.referral_count or 0,
            "earnings": user.referral_earnings or 0
        }

async def add_billing_record(tg_id: int, amount: int, record_type: str, description: str = ""):
    """添加消费/充值记录 type: purchase/topup/refund/referral"""
    from src.database.models import Transaction
    async with async_session() as session:
        record = Transaction(
            user_id=tg_id,
            amount=amount,
            description=description
        )
        session.add(record)
        await session.commit()

async def get_billing_records(tg_id: int, limit: int = 10):
    """获取用户最近消费记录"""
    from src.database.models import Transaction
    async with async_session() as session:
        result = await session.scalars(
            select(Transaction)
            .where(Transaction.user_id == tg_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
        )
        return result.all()
