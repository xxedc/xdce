from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.services.stats import collect_daily_stats

scheduler = AsyncIOScheduler()

async def check_expiring_subscriptions():
    """每天检查即将到期的订阅，发送提醒"""
    from src.database.core import async_session
    from src.database.models import Subscription, User
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from datetime import datetime, timedelta
    from src.bot import bot
    from loguru import logger

    now = datetime.now()
    remind_days = [3, 1, 0]  # 提前3天、1天、当天提醒

    async with async_session() as session:
        result = await session.scalars(
            select(Subscription)
            .options(joinedload(Subscription.user))
            .where(Subscription.expires_at > now)
        )
        subs = result.all()

    for sub in subs:
        days_left = (sub.expires_at - now).days
        if days_left not in remind_days:
            continue

        user = sub.user
        if not user:
            continue

        # 跳过永久套餐
        if days_left >= 3640:
            continue

        # 根据剩余天数选择消息
        if days_left == 0:
            emoji = "🚨"
            title = "订阅今天到期！"
            urgency = "您的订阅<b>今天到期</b>，到期后将无法使用，请立即续费！"
        elif days_left == 1:
            emoji = "⚠️"
            title = "订阅明天到期"
            urgency = "您的订阅<b>明天到期</b>，请及时续费以避免中断。"
        else:
            emoji = "🔔"
            title = "订阅即将到期"
            urgency = "您的订阅还有 <b>" + str(days_left) + " 天</b>到期，记得提前续费哦！"

        expire_str = sub.expires_at.strftime("%Y-%m-%d %H:%M")
        sub_url = sub.subscription_url if hasattr(sub, 'subscription_url') and sub.subscription_url else ""

        msg = (
            emoji + " <b>" + title + "</b>\n\n"
            + urgency + "\n\n"
            "⏳ 到期时间：" + expire_str + "\n\n"
            "💡 续费方式：点击下方 ⚡ 购买VPN 按钮选择套餐续费\n"
        )
        if sub_url:
            msg += "\n📋 您的订阅链接：\n<code>" + sub_url + "</code>"

        try:
            await bot.send_message(
                chat_id=user.id,
                text=msg,
                parse_mode="HTML"
            )
            logger.info("🔔 已发送到期提醒给用户 " + str(user.id) + "，剩余 " + str(days_left) + " 天")
        except Exception as e:
            logger.warning("发送提醒失败 用户" + str(user.id) + ": " + str(e))



async def sync_subscription_urls():
    """每天同步 Marzban 最新订阅链接到数据库"""
    from src.database.core import async_session
    from src.database.models import Subscription
    from src.services.marzban_api import api
    from sqlalchemy import select
    import aiohttp
    from loguru import logger

    async with async_session() as session:
        subs = (await session.scalars(select(Subscription))).all()
        for sub in subs:
            if not sub.marzban_username:
                continue
            try:
                headers = await api._headers()
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(
                        api.host + "/api/user/" + sub.marzban_username,
                        headers=headers
                    ) as r:
                        if r.status == 200:
                            data = await r.json()
                            new_url = data.get("subscription_url", "")
                            if new_url and not new_url.startswith("http"):
                                new_url = api.host + new_url
                            if new_url:
                                sub.subscription_url = new_url
            except Exception as e:
                logger.warning("同步订阅链接失败: " + str(e))
        await session.commit()
        logger.info("✅ 订阅链接同步完成")


async def sync_marzban_settings():
    """根据用户当前有效套餐，同步正确的设置到 Marzban"""
    from src.database.core import async_session
    from src.database.models import Subscription, User
    from src.services.marzban_api import api
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from datetime import datetime
    from loguru import logger
    import aiohttp

    now = datetime.now()

    async with async_session() as session:
        # 获取所有用户
        users = (await session.scalars(select(User))).all()

    for user in users:
        async with async_session() as session:
            subs = (await session.scalars(
                select(Subscription).where(Subscription.user_id == user.id)
            )).all()

        active_time = None
        active_traffic = None
        marzban_username = None

        for s in subs:
            if not marzban_username and s.marzban_username:
                marzban_username = s.marzban_username
            pt = getattr(s, 'plan_type', 'time')
            if pt == 'time' and s.expires_at > now:
                if active_time is None or s.expires_at > active_time.expires_at:
                    active_time = s
            elif pt == 'traffic':
                active_traffic = s

        if not marzban_username:
            continue

        try:
            headers = await api._headers()

            if active_time and active_traffic:
                # 同时有时间套餐和流量包
                # 时间套餐优先：200GB/月重置，有到期时间
                # 流量包保存在数据库，等时间套餐到期后自动激活
                expire_ts = int(active_time.expires_at.timestamp())
                payload = {
                    "expire": expire_ts,
                    "data_limit": int((30 if marzban_username.startswith("trial_") else 200) * 1024**3),
                    "data_limit_reset_strategy": "month",
                    "status": "active"
                }

            elif active_time:
                # 只有时间套餐：200GB每月重置
                expire_ts = int(active_time.expires_at.timestamp())
                payload = {
                    "expire": expire_ts,
                    "data_limit": int((30 if marzban_username.startswith("trial_") else 200) * 1024**3),
                    "data_limit_reset_strategy": "month",
                    "status": "active"
                }

            elif active_traffic:
                # 只有流量包：不限时间，总GB用完即止，不重置
                traffic_gb = getattr(active_traffic, 'traffic_gb', 0) or 500
                payload = {
                    "expire": 0,
                    "data_limit": int(traffic_gb * 1024**3),
                    "data_limit_reset_strategy": "no_reset",
                    "status": "active"
                }

            else:
                # 没有有效套餐：禁用
                payload = {"status": "disabled"}

            async with aiohttp.ClientSession() as sess:
                async with sess.put(
                    api.host + "/api/user/" + marzban_username,
                    json=payload,
                    headers=headers
                ) as r:
                    result = await r.json()
                    logger.info("同步 " + marzban_username + " -> " + str(payload.get("status", "active")))

        except Exception as e:
            logger.warning("同步 Marzban 设置失败 " + marzban_username + ": " + str(e))


async def send_daily_group_message():
    """每天发送不同消息到群组"""
    from src.bot import bot
    from datetime import datetime
    from loguru import logger

    GROUP_ID = -1003798316924
    BOT_LINK = "@Dcxxe_bot"

    weekday = datetime.now().weekday()  # 0=周一 6=周日

    messages = {
        0: (  # 周一：节点状态
            "🌐 <b>本周节点状态</b>\n\n"
            "🟢 全球通：正常运行\n"
            "⚡ 平均延迟：18ms\n"
            "📶 可用节点：全部正常\n\n"
            "💡 连接慢？切换节点试试\n"
            "👉 " + BOT_LINK
        ),
        1: (  # 周二：签到提醒
            "📅 <b>每日签到提醒</b>\n\n"
            "今日签到可获得：<b>+5GB</b> 流量\n"
            "连续7天额外：<b>+15GB</b> 🎁\n"
            "连续30天额外：<b>+20GB</b> 🏆\n\n"
            "👉 " + BOT_LINK + " 立即签到"
        ),
        2: (  # 周三：邀请返利
            "👥 <b>邀请好友赚钱</b>\n\n"
            "好友注册 → <b>+5¥</b>\n"
            "好友购买 → <b>10%返佣</b>\n"
            "还能延长<b>7天</b>订阅！\n\n"
            "👉 " + BOT_LINK + " 获取邀请链接"
        ),
        3: (  # 周四：套餐介绍
            "💰 <b>套餐价格一览</b>\n\n"
            "🗓 1个月  <b>15¥</b> / 200GB\n"
            "🗓 3个月  <b>40¥</b> / 600GB 🔥\n"
            "🗓 12个月 <b>140¥</b> 最划算 👑\n"
            "📦 流量包 <b>35¥</b> / 500GB\n\n"
            "👉 " + BOT_LINK + " 立即购买"
        ),
        4: (  # 周五：协议介绍
            "🔐 <b>支持全部主流协议</b>\n\n"
            "✔ VLESS Reality（最强抗封锁）\n"
            "✔ VMess / Trojan\n"
            "✔ Shadowsocks\n\n"
            "📱 支持所有设备\n"
            "iOS / Android / Windows / Mac\n\n"
            "👉 " + BOT_LINK + " 免费试用7天"
        ),
        5: (  # 周六：用户福利
            "🎁 <b>本周福利提醒</b>\n\n"
            "📅 每日签到最高 <b>+15GB</b>\n"
            "📢 加入群组领 <b>+20GB</b>\n"
            "👥 邀请1人得 <b>+5¥</b>\n\n"
            "还没领取的快来！\n"
            "👉 " + BOT_LINK
        ),
        6: (  # 周日：免费试用
            "🆓 <b>新用户免费试用</b>\n\n"
            "注册即送 <b>7天 + 30GB</b>\n"
            "加入群组再送 <b>20GB</b>\n\n"
            "全球节点 · 不限速\n"
            "支持5台设备同时使用\n\n"
            "👉 " + BOT_LINK + " 立即体验"
        ),
    }

    msg = messages.get(weekday, messages[0])

    try:
        await bot.send_message(GROUP_ID, msg, parse_mode="HTML")
        logger.info("✅ 每日群组消息发送成功 weekday=" + str(weekday))
    except Exception as e:
        logger.warning("❌ 每日群组消息发送失败: " + str(e))


def start_scheduler():
    # 每天 10:00 执行统计
    scheduler.add_job(collect_daily_stats, 'cron', hour=10, minute=0)

    # 每天 09:00 检查到期提醒（北京时间需+8，服务器UTC时间01:00）
    scheduler.add_job(
        check_expiring_subscriptions,
        'cron',
        hour=1,   # UTC 01:00 = 北京时间 09:00
        minute=0
    )

    scheduler.start()
