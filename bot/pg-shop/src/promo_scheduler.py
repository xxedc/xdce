"""
DC加速 - 定时推广发送
- 每天 9 / 13 / 17 / 21 点(北京时间)发送
- 12 套图随机选,7 天内不重复
- 每张图配 3 套不同文案,随机抽
- 每次发送都创建新临时账号(12 小时,5GB)
"""
import asyncio
import os
import random
import sqlite3
import time

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.config import settings
from src.services.marzban_api import api as pg_api

# ============== 配置 ==============
GROUP_ID = -1003798316924
CHANNEL_ID = -1003976390464
BOT_USERNAME = "dcxxe_bot"
GROUP_LINK = "https://t.me/DCxxeo"

PROMO_DIR = "/opt/pg-shop/promo_images"
PROMO_DB = "/opt/pg-shop/promo_history.db"

TRIAL_HOURS = 12
TRIAL_GB = 5

# 每天 1 次推广,在 8:00-22:00 之间随机选一个时间
SCHEDULE_HOURS = []  # 不再使用固定时间,由 _schedule_random_promo 动态调度

IMAGE_KEYS = [
    "01_global", "02_bandwidth", "03_dedicated", "04_streaming",
    "05_netflix", "06_gaming", "07_multidevice", "08_anticensor",
    "09_privacy", "10_monthly", "11_quarterly", "12_yearly",
]

CAPTIONS = {
    "01_global": [
        "🌐 <b>全球节点 · 一键解锁全世界</b>\n\n哪里都能去,哪里都不卡。\n月套餐 ¥15 起,新人首单立享 7 天试用。",
        "🌐 <b>覆盖全球的优质节点</b>\n\n美国 / 日本 / 香港 / 新加坡 / 德国...\n一个号通用所有线路,想去哪去哪。",
        "🌐 <b>畅游互联网,无国界</b>\n\n全球节点任意切换,5 设备同时在线。\n点击下方按钮,立即开始体验。",
    ],
    "02_bandwidth": [
        "🚀 <b>独享带宽 · 不与人共享</b>\n\n千兆专线,晚高峰也满速。\n告别共享带宽的拥堵,拥有属于自己的专属通道。",
        "🚀 <b>带宽独享,体验升级</b>\n\n别人挤公交,你坐专车。\n不限速,无拥堵,看 4K 都流畅。",
        "🚀 <b>真正的独享带宽</b>\n\n千兆带宽 · 晚高峰不限速 · 低延迟\n告别其他机场的虚标带宽,体验真满速。",
    ],
    "03_dedicated": [
        "⚡ <b>专线加速 · 告别绕路</b>\n\nIPLC 国际专线 + BGP 智能路由\n三网优化,直连无延迟。",
        "⚡ <b>国际专线 · 极速直达</b>\n\n不走公网拥堵线路,IPLC 专线直连。\n移动 / 联通 / 电信 三网优化。",
        "⚡ <b>骨干网级别的专线</b>\n\n听说过 IPLC 吗?这就是。\n稳定低延迟,游戏党 / 商务党 必备。",
    ],
    "04_streaming": [
        "🎬 <b>4K 流媒体 · 零卡顿</b>\n\n油管 4K 不缓冲,B 站港区原生解锁。\nTikTok 一键直通,内容自由享受。",
        "🎬 <b>看视频不再卡</b>\n\n油管 4K · TikTok · B 站港区,统统流畅。\n下班路上、午休时间,都能尽情刷。",
        "🎬 <b>视频党的最佳选择</b>\n\n4K 60fps 不掉帧,弹幕不延迟。\n全平台原生解锁,内容自由探索。",
    ],
    "05_netflix": [
        "📺 <b>解锁追剧 · 原生 IP</b>\n\nNetflix · Disney+ · HBO · Hulu · Prime\n全平台原生解锁,自制剧第一时间看。",
        "📺 <b>奈飞党专属</b>\n\n原生 IP 解锁,看自制剧不再被锁区。\n港区 / 日区 / 美区,任意切换。",
        "📺 <b>追剧无国界</b>\n\nNetflix 4K · Disney+ · HBO Max\n原生节点不止解锁,还很流畅。",
    ],
    "06_gaming": [
        "🎮 <b>原生 IP · 稳如老狗</b>\n\n游戏竞技直连原生节点,加密链路零日志。\n年卡立省 22%,锁定一年低价。",
        "🎮 <b>游戏党的福音</b>\n\n低延迟原生 IP,Apex / 战地 / Steam 流畅。\n稳如老狗,从此告别卡顿掉线。",
        "🎮 <b>电竞级低延迟</b>\n\nPing 值低到感动,操作丝滑跟手。\n重要团战不掉线,稳定就是赢。",
    ],
    "07_multidevice": [
        "📱 <b>一号通用 · 5 端齐发</b>\n\n手机 / 平板 / 电脑 / 路由器,通通能用。\niOS · 安卓 · Win · Mac 全平台支持。",
        "📱 <b>全家都能用</b>\n\n一个账号 5 个设备同时在线。\n夫妻、家人、室友 共享更划算。",
        "📱 <b>一号走天下</b>\n\n5 设备同登,全平台覆盖。\n一次购买,全屋畅游。",
    ],
    "08_anticensor": [
        "🛡 <b>抗封锁强 · 稳定不掉</b>\n\nReality 黑科技 + 节点自动切换。\n重大节日不掉线,关键时刻不掉链子。",
        "🛡 <b>关键时刻不掉链</b>\n\n敏感时期、节假日 加强抗封锁。\n备用节点自动切换,永远在线。",
        "🛡 <b>稳定才是硬道理</b>\n\nReality 协议抗封锁,被打了立刻换线。\n别人在掉线,你在畅游。",
    ],
    "09_privacy": [
        "🔒 <b>加密链路 · 零日志</b>\n\nTLS 1.3 全程加密,无流量日志,无用户信息留存。\n你的隐私,只属于你。",
        "🔒 <b>真正的隐私保护</b>\n\n零日志政策 + 端到端加密。\n我们不知道你访问了什么,也不想知道。",
        "🔒 <b>隐私第一</b>\n\nTLS 1.3 加密 + 严格无日志。\n企业级安全,个人级体验。",
    ],
    "10_monthly": [
        "🎁 <b>月卡 ¥15 · 一杯奶茶钱</b>\n\n200GB 流量包月,新用户首月体验。\n少喝一杯奶茶,多一个月畅游全球。",
        "🎁 <b>15 块钱能干啥?</b>\n\n一杯奶茶 / 一顿外卖 / 或者 ... 一整月畅游互联网。\n性价比之王,试一次就回不去。",
        "🎁 <b>月卡新人价 ¥15</b>\n\n200GB 流量,5 设备同登,全球节点。\n这价格,真不亏。",
    ],
    "11_quarterly": [
        "🔥 <b>季卡省 11%</b>\n\n3 个月仅 ¥40,平均每月 ¥13。\n锁定低价,送 7 天试用期。",
        "🔥 <b>买季卡更划算</b>\n\n比月卡省 11%,平均下来一月 ¥13。\n短期党、上班族、学生党 首选。",
        "🔥 <b>3 个月套餐 ¥40</b>\n\n锁定当前价格,3 个月不涨价。\n买三个月,享 7 天试用,亏不了。",
    ],
    "12_yearly": [
        "👑 <b>年卡省 22% · 一步到位</b>\n\n全年 ¥140,平均每月 ¥11.6。\nVIP 优先客服,一年无忧。",
        "👑 <b>一年只要 ¥140</b>\n\n比月卡省 22%,锁定全年低价。\n长期党 / 重度用户 / 性价比党 必选。",
        "👑 <b>VIP 年卡</b>\n\n全年畅游,优先客服,优先排队。\n买一次,爽一年。",
    ],
}


def get_token():
    t = settings.BOT_TOKEN
    if hasattr(t, "get_secret_value"):
        return t.get_secret_value()
    return t


def init_promo_db():
    conn = sqlite3.connect(PROMO_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS promo_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_key TEXT NOT NULL,
            sent_at INTEGER NOT NULL,
            target TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def pick_image_key():
    init_promo_db()
    conn = sqlite3.connect(PROMO_DB)
    week_ago = int(time.time()) - 7 * 86400
    rows = conn.execute(
        "SELECT image_key FROM promo_history WHERE sent_at > ?",
        (week_ago,)
    ).fetchall()
    used = {r[0] for r in rows}
    available = [k for k in IMAGE_KEYS if k not in used]
    if available:
        chosen = random.choice(available)
    else:
        row = conn.execute(
            "SELECT image_key, MIN(sent_at) FROM promo_history "
            "GROUP BY image_key ORDER BY MIN(sent_at) ASC LIMIT 1"
        ).fetchone()
        chosen = row[0] if row else random.choice(IMAGE_KEYS)
    conn.close()
    return chosen


def record_sent(image_key, target):
    conn = sqlite3.connect(PROMO_DB)
    conn.execute(
        "INSERT INTO promo_history (image_key, sent_at, target) VALUES (?,?,?)",
        (image_key, int(time.time()), target)
    )
    conn.commit()
    conn.close()


async def create_trial_subscription():
    username = f"promo_{int(time.time())}_{random.randint(100, 999)}"
    expire_ts = int(time.time()) + TRIAL_HOURS * 3600
    try:
        _, sub_url = await pg_api.create_key(
            username=username,
            expire_timestamp=expire_ts,
            data_limit_gb=TRIAL_GB,
        )
        return sub_url, username
    except Exception as e:
        logger.error(f"创建临时订阅失败: {e}")
        return "", ""


def build_caption(image_key, sub_url):
    captions = CAPTIONS.get(image_key, ["🚀 <b>DC加速</b>\n\n点击下方按钮,立即体验。"])
    base = random.choice(captions)
    if sub_url:
        return (
            f"{base}\n\n"
            f"━━━━━━━━━━━━\n"
            f"🎁 <b>{TRIAL_HOURS} 小时免费体验</b> · {TRIAL_GB}GB 流量\n"
            f"<code>{sub_url}</code>\n\n"
            f"⚠️ 链接有效期 {TRIAL_HOURS} 小时,先到先得"
        )
    else:
        return f"{base}\n\n🚀 点击下方按钮,联系客服开通"


def build_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 立即购买", url=f"https://t.me/{BOT_USERNAME}"),
            InlineKeyboardButton(text="💬 加入群组", url=GROUP_LINK),
        ]
    ])

async def send_promo_once():
    # 发送前先清理过期 trial 账号
    try:
        deleted = await pg_api.cleanup_expired_trials("promo_")
        if deleted > 0:
            logger.info(f"🗑 已清理过期 trial 账号: {deleted} 个")
    except Exception as e:
        logger.warning(f"清理过期账号失败(不影响发送): {e}")

    image_key = pick_image_key()
    image_path = os.path.join(PROMO_DIR, f"{image_key}.jpg")
    if not os.path.exists(image_path):
        logger.error(f"图片不存在: {image_path}")
        return
    sub_url, trial_user = await create_trial_subscription()
    caption = build_caption(image_key, sub_url)
    keyboard = build_keyboard()
    bot = Bot(get_token())
    try:
        for target_id, target_name in [(GROUP_ID, "group"), (CHANNEL_ID, "channel")]:
            try:
                photo = FSInputFile(image_path)
                await bot.send_photo(
                    chat_id=target_id,
                    photo=photo,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
                record_sent(image_key, target_name)
                logger.info(f"✅ 推广已发送 [{image_key}] -> {target_name} (trial: {trial_user})")
            except Exception as e:
                logger.error(f"发送到 {target_name} 失败: {e}")
    finally:
        await bot.session.close()




def _schedule_next_random(scheduler):
    """安排明天某个随机时间发送推广(8:00-22:00 之间)"""
    from datetime import datetime, timedelta
    import random as _r
    import pytz as _pytz

    tz = _pytz.timezone("Asia/Shanghai")
    now = datetime.now(tz)

    # 计算明天 8:00-22:00 之间的随机时间点
    tomorrow = now + timedelta(days=1)
    random_hour = _r.randint(8, 22)
    random_minute = _r.randint(0, 59)
    next_run = tomorrow.replace(
        hour=random_hour, minute=random_minute, second=0, microsecond=0
    )

    async def _wrapped():
        await send_promo_once()
        # 发完后立刻安排下一天的随机时间
        _schedule_next_random(scheduler)

    scheduler.add_job(
        _wrapped,
        "date",
        run_date=next_run,
        id=f"promo_random_{int(next_run.timestamp())}",
        replace_existing=True,
    )
    logger.info(f"📅 下次推广已排期: {next_run.strftime('%Y-%m-%d %H:%M')} (北京时间)")


def setup_promo_scheduler():
    """启动随机时间推广调度器"""
    from datetime import datetime, timedelta
    import random as _r
    import pytz as _pytz

    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

    # 当天:如果还没过 22 点,就在 现在+30分钟 到 22:00 之间随机选个时间发
    tz = _pytz.timezone("Asia/Shanghai")
    now = datetime.now(tz)

    if now.hour < 22:
        # 今天还有时间发
        earliest = now + timedelta(minutes=30)
        latest = now.replace(hour=22, minute=0, second=0, microsecond=0)
        if earliest < latest:
            delta_seconds = int((latest - earliest).total_seconds())
            random_offset = _r.randint(0, delta_seconds)
            today_run = earliest + timedelta(seconds=random_offset)

            async def _today_wrapped():
                await send_promo_once()
                _schedule_next_random(scheduler)

            scheduler.add_job(
                _today_wrapped,
                "date",
                run_date=today_run,
                id="promo_today",
                replace_existing=True,
            )
            logger.info(f"📅 今日推广已排期: {today_run.strftime('%H:%M')} (北京时间)")
        else:
            # 今天来不及,明天发
            _schedule_next_random(scheduler)
    else:
        # 已经过 22 点,明天发
        _schedule_next_random(scheduler)

    scheduler.start()
    return scheduler




# ============== /promo 手动触发命令 ==============
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

promo_router = Router()
ADMIN_IDS = [8171456258]  # 你的 TG 数字 ID


@promo_router.message(Command("promo"))
async def cmd_promo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("⏳ 正在手动触发推广发送...")
    try:
        await send_promo_once()
        await message.answer("✅ 推广已发送到群组和频道!")
    except Exception as e:
        await message.answer(f"❌ 发送失败:{e}")
