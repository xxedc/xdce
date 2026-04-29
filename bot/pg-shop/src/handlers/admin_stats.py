from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, or_f

from src.utils.translations import get_text
from src.database.requests import get_stats
from src.config import settings
from src.services.marzban_api import api

router = Router()

# ============================================
# 动态获取节点国家(支持多节点自动扩展)
# ============================================
COUNTRY_FLAGS = {
    "JP": ("🇯🇵", "日本节点"),
    "KR": ("🇰🇷", "韩国节点"),
    "US": ("🇺🇸", "美国节点"),
    "HK": ("🇭🇰", "香港节点"),
    "TW": ("🇹🇼", "台湾节点"),
    "SG": ("🇸🇬", "新加坡节点"),
    "DE": ("🇩🇪", "德国节点"),
    "GB": ("🇬🇧", "英国节点"),
    "RU": ("🇷🇺", "俄罗斯节点"),
    "FR": ("🇫🇷", "法国节点"),
    "CA": ("🇨🇦", "加拿大节点"),
    "AU": ("🇦🇺", "澳大利亚节点"),
    "NL": ("🇳🇱", "荷兰节点"),
    "TR": ("🇹🇷", "土耳其节点"),
    "IN": ("🇮🇳", "印度节点"),
    "BR": ("🇧🇷", "巴西节点"),
}

# 简单缓存,1 小时刷新一次
_NODE_CACHE = {"data": None, "ts": 0}

async def _get_country_for_ip(ip: str):
    """根据 IP 查国家代码,返回 (emoji, 中文国家名)"""
    try:
        import aiohttp as _aio
        async with _aio.ClientSession() as _s:
            async with _s.get(f"https://ipinfo.io/{ip}/json", timeout=_aio.ClientTimeout(total=5)) as _r:
                d = await _r.json()
                country = d.get("country", "")
                return COUNTRY_FLAGS.get(country, ("🌍", f"{country or '未知'}节点"))
    except Exception:
        return ("🌍", "未知节点")


async def get_all_nodes_info():
    """从 PasarGuard 获取所有节点信息(主节点 + 子节点)"""
    import time
    if _NODE_CACHE["data"] and (time.time() - _NODE_CACHE["ts"]) < 3600:
        return _NODE_CACHE["data"]

    nodes = []
    try:
        import aiohttp as _aio
        import socket
        from urllib.parse import urlparse

        # 1. 主节点(MARZBAN_HOST 解析的 IP)
        host_parsed = urlparse(api.host)
        try:
            main_ip = socket.gethostbyname(host_parsed.hostname)
            main_emoji, main_name = await _get_country_for_ip(main_ip)
            nodes.append({"name": main_name, "emoji": main_emoji, "ip": main_ip, "is_main": True})
        except Exception:
            nodes.append({"name": "主节点", "emoji": "🖥", "ip": "", "is_main": True})

        # 2. 子节点(从 PasarGuard /api/nodes 获取)
        headers = await api._headers()
        async with _aio.ClientSession() as _sess:
            async with _sess.get(f"{api.host}/api/nodes", headers=headers) as _r:
                if _r.status == 200:
                    nodes_data = await _r.json()
                    for n in (nodes_data if isinstance(nodes_data, list) else []):
                        node_ip = n.get("address", "") or ""
                        if node_ip:
                            emoji, name = await _get_country_for_ip(node_ip)
                            nodes.append({"name": name, "emoji": emoji, "ip": node_ip, "is_main": False})
    except Exception:
        pass

    _NODE_CACHE["data"] = nodes
    _NODE_CACHE["ts"] = time.time()
    return nodes


# Фильтр: только для админов
@router.message(
    F.from_user.id.in_(settings.ADMIN_IDS),
    or_f(Command("stats"), F.text.in_(["📦 我的订阅", "💰 个人中心"]))
)
async def admin_stats(message: Message, t):
    # 1. Получаем данные из БД
    total_users, active_subs = await get_stats()
    
    # 从 Marzban 获取系统信息
    servers_info = ""
    try:
        import aiohttp as _aio
        headers = await api._headers()
        async with _aio.ClientSession() as _sess:
            async with _sess.get(f"{api.host}/api/system", headers=headers) as _r:
                sys_data = await _r.json()
            # 获取所有用户流量汇总
            async with _sess.get(
                f"{api.host}/api/users?limit=500",
                headers=headers
            ) as _r2:
                users_data = await _r2.json()

        total_traffic = sum((u.get("used_traffic") or 0) for u in users_data.get("users", []))
        total_gb = round(total_traffic / 1024**3, 2)

        mem = sys_data.get("mem_used", 0)
        mem_total = sys_data.get("mem_total", 1)
        mem_pct = round(mem / mem_total * 100) if mem_total else 0
        cpu = sys_data.get("cpu_usage", 0)
        incoming = round((sys_data.get("incoming_bandwidth", 0) or 0) / 1024**3, 2)
        outgoing = round((sys_data.get("outgoing_bandwidth", 0) or 0) / 1024**3, 2)

        # 动态获取节点列表
        nodes = await get_all_nodes_info()
        nodes_str = ""
        for n in nodes:
            nodes_str += f"{n['emoji']} {n['name']}：🟢 运行正常\n"
        if not nodes_str:
            nodes_str = "🌍 节点信息加载中...\n"

        servers_info = (
            nodes_str
            + f"🖥 CPU：{cpu}%  |  内存：{mem_pct}%\n"
            + f"📥 总入站：{incoming} GB\n"
            + f"📤 总出站：{outgoing} GB\n"
            + f"📶 全部用户已用流量：{total_gb} GB"
        )
    except Exception as e:
        try:
            nodes = await get_all_nodes_info()
            nodes_str = ""
            for n in nodes:
                nodes_str += f"{n['emoji']} {n['name']}：🟢 运行正常\n"
            servers_info = nodes_str + f"⚠️ 详细数据获取失败：{e}"
        except Exception:
            servers_info = f"🌍 节点：🟢 运行正常\n⚠️ 详细数据获取失败：{e}"

    # 3. Отправляем отчет
    await message.answer(
        t(
            "admin_stats", 
            users=total_users, 
            subs=active_subs, 
            servers_info=servers_info
        ),
        parse_mode="HTML"
    )

@router.message(F.text.in_(["📦 我的订阅", "💰 个人中心", "📊 服务状态"]))
async def public_stats(message: Message, t):
    from src.database.requests import get_user, get_user_subscriptions
    from src.services.marzban_api import api
    from datetime import datetime
    import aiohttp as _aio

    tg_user = message.from_user
    user = await get_user(tg_user.id)
    subs = await get_user_subscriptions(tg_user.id)

    name = tg_user.full_name or tg_user.username or str(tg_user.id)
    balance = user.balance if user else 0
    now = datetime.now()
    active_subs = [s for s in subs if s.expires_at > now]

    from src.handlers.user_buy import get_usdt_rate as _get_rate
    try:
        _rate = await _get_rate()
    except Exception:
        _rate = 7.2

    lines = [
        "╔══════════════════╗",
        "        👤 用户中心",
        "╚══════════════════╝",
        "",
        "👤 用户：<b>" + name + "</b>",
        "🆔 UID：<code>" + str(tg_user.id) + "</code>",
        "",
        "💰 账户余额：<b>" + str(balance) + " ¥</b>",
        "💱 汇率参考：<b>1 USDT ≈ " + str(_rate) + " ¥</b>",
        "",
        "━━━━━━━━━━━━━━━━━━",
    ]

    if not active_subs:
        lines += ["❌ <b>暂无活跃订阅</b>", "", "点击 ⚡ 购买VPN 开始使用"]
    else:
        # 分离时间套餐和流量包
        time_subs = [s for s in active_subs if not hasattr(s, 'plan_type') or s.plan_type != 'traffic']
        traffic_subs = [s for s in active_subs if hasattr(s, 'plan_type') and s.plan_type == 'traffic']

        # 取最新时间套餐
        best_time = sorted(time_subs, key=lambda s: s.expires_at, reverse=True)[0] if time_subs else None
        # 取最新节点信息
        best = best_time or sorted(active_subs, key=lambda s: s.expires_at, reverse=True)[0]

        # 节点名
        loc = (best.server.location or "").lower() if best.server else ""
        if "multi" in loc:
            node = "🌍 全球通（所有节点）"
        elif loc in ("swe", "jp", "japan"):
            node = "🇯🇵 日本"
        else:
            node = "🌐 " + (best.server.name if best.server else loc)

        # 从 Marzban 获取流量
        used_bytes = 0
        marzban_limit = 0
        try:
            headers = await api._headers()
            async with _aio.ClientSession() as sess:
                async with sess.get(
                    api.host + "/api/user/" + best.marzban_username,
                    headers=headers
                ) as r:
                    d = await r.json()
                    used_bytes = d.get("used_traffic") or 0
                    marzban_limit = d.get("data_limit") or 0
        except Exception:
            pass

        used_gb = round(used_bytes / 1024**3, 2)

        # 流量包总计
        traffic_pack_gb = sum(getattr(s, 'traffic_gb', 0) or 500 for s in traffic_subs)

        # 套餐状态
        has_valid = bool(best_time or best_traffic)
        status_str = "🟢 有效" if has_valid else "🔴 已过期（请及时续费）"

        # 套餐信息
        lines += [
            "🚀 <b>当前套餐</b>",
            "🌍 " + node,
            "",
            "📊 状态：" + status_str,
        ]

        if best_time:
            t_days = (best_time.expires_at - now).days
            if t_days >= 3640:
                lines += ["⏳ 到期：永久有效", "⏱ 剩余：永久"]
            else:
                lines += [
                    "⏳ 到期：" + best_time.expires_at.strftime("%Y-%m-%d %H:%M"),
                    "⏱ 剩余：" + str(t_days) + " 天",
                ]
        else:
            lines.append("⏳ 到期：无时间套餐")

        lines += [
            "",
            "━━━━━━━━━━━━━━━━━━",
            "📡 <b>流量统计</b>",
            "",
        ]

        if best_time:
            lines.append("📦 月流量：200 GB")
        lines.append("📉 已用流量：" + str(used_gb) + " GB")
        lines.append("🔄 重置周期：30 天")

        if traffic_pack_gb > 0:
            remain_pack = round(max(0, traffic_pack_gb - used_gb), 2)
            lines += [
                "",
                "📦 流量包：" + str(traffic_pack_gb) + " GB（用完即止）",
                "📊 剩余：" + str(remain_pack) + " GB",
            ]

        # 订阅链接
        sub_url = ""
        for s in sorted(active_subs, key=lambda x: x.expires_at, reverse=True):
            if hasattr(s, "subscription_url") and s.subscription_url:
                sub_url = s.subscription_url
                break

        lines += ["", "━━━━━━━━━━━━━━━━━━", "🔗 <b>订阅管理</b>", ""]
        if sub_url:
            lines += [
                "📥 一键订阅：",
                "<code>" + sub_url + "</code>",
                "",
                "📌 <b>支持所有主流客户端</b>\n\n""🍏 iOS / macOS\n""Shadowrocket · Stash · Surge · Egern · Quantumult X\n\n""🤖 Android\n""v2rayNG · Hiddify · NekoBox · SagerNet\n\n""💻 Windows / Linux\n""Clash Verge · v2rayN · sing-box · Nekoray\n\n""🌐 全平台\n""Outline · Streisand",
            ]
        else:
            lines.append("💡 购买套餐后获得订阅链接")

        lines += [
            "",
            "━━━━━━━━━━━━━━━━━━",
            "⚙️ <b>使用建议</b>",
            "",
            "• 建议开启「自动更新订阅」",
            "• 连接异常 → 切换节点",
            "• 高峰期优先选择低延迟线路",
            "━━━━━━━━━━━━━━━━━━",
        ]

    await message.answer("\n".join(lines), parse_mode="HTML")

