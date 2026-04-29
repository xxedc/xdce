from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.utils.translations import get_text

def buy_type_kb(lang: str = "ru", rate: float = 7.2):
    builder = InlineKeyboardBuilder()
    builder.button(text=get_text(lang, "btn_multi"), callback_data="buy_multi")
    builder.adjust(1)
    return builder.as_markup()

def location_kb(lang: str = "ru", prefix: str = "buy"):
    builder = InlineKeyboardBuilder()
    builder.button(text=get_text(lang, "swe"), callback_data=f"{prefix}_swe")
    builder.button(text=get_text(lang, "ger"), callback_data=f"{prefix}_ger")
    
    # 只在购买时显示返回按钮
    if prefix == "buy":
        builder.button(text=get_text(lang, "btn_back"), callback_data="back_to_types")
        
    builder.adjust(1)
    return builder.as_markup()

def duration_kb(lang: str, location_code: str, rate: float = 7.2):
    builder = InlineKeyboardBuilder()

    def u(cny): return round(cny / rate, 2)

    plans = [
        (30,  200,  15,  "🗓 1个月 — 15¥ / " + str(u(15)) + " USDT（200GB）"),
        (90,  600,  40,  "🗓 3个月 — 40¥ / " + str(u(40)) + " USDT 🔥 省11%"),
        (180, 1200, 75,  "🗓 6个月 — 75¥ / " + str(u(75)) + " USDT 🔥 省17%"),
        (365, 2400, 140, "🗓 12个月 — 140¥ / " + str(u(140)) + " USDT 👑 省22%"),
        (0,   500,  35,  "📦 流量包 — 35¥ / " + str(u(35)) + " USDT（500GB）"),
    ]

    for days, traffic_gb, price, label in plans:
        builder.button(
            text=label,
            callback_data=f"prepay_{location_code}_{days}_{price}"
        )

    back_callback = "back_to_types" if location_code == "multi" else "type_single"
    builder.button(text=get_text(lang, "btn_back"), callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()

def payment_method_kb(lang: str, balance: int, price: int, location_code: str, days: int):
    builder = InlineKeyboardBuilder()
    
    # 1. 余额支付
    if balance >= price:
        # 余额充足 → 按钮激活
        builder.button(
            text=get_text(lang, "pay_balance_btn", price=price),
            callback_data=f"confirm_balance_{location_code}_{days}_{price}"
        )
    else:
        # 余额不足 → 跳转充值
        diff = price - balance
        builder.button(
            text=get_text(lang, "pay_balance_disabled", diff=diff),
            callback_data=f"top_up_buy_{location_code}_{days}_{price}"
        )

    # 2. 在线支付（始终可用）
    builder.button(
        text=get_text(lang, "pay_online_btn", price=price),
        callback_data=f"confirm_online_{location_code}_{days}_{price}"
    )
    
    builder.button(text=get_text(lang, "btn_back"), callback_data=f"buy_{location_code}")
    builder.adjust(1)
    return builder.as_markup()

def top_up_kb(lang: str, back_callback: str = "back_to_profile", context_suffix: str = ""):
    builder = InlineKeyboardBuilder()
    amounts = [100, 200, 300, 500, 1000]
    for amount in amounts:
        # 如有购买上下文则附加到 callback
        builder.button(text=f"{amount}₽", callback_data=f"add_funds_{amount}{context_suffix}")
    builder.button(text=get_text(lang, "btn_back"), callback_data=back_callback)
    builder.adjust(2)
    return builder.as_markup()

def language_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇨🇳 中文", callback_data="lang_zh")
    builder.button(text="🇬🇧 English", callback_data="lang_en")
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.adjust(2)
    return builder.as_markup()

def profile_kb(lang: str = "zh", has_active_sub: bool = False):
    """新版我的订阅页按钮(去掉 iOS/Android/Windows,改成正确 callback)"""
    builder = InlineKeyboardBuilder()

    if has_active_sub:
        # 续费(直接跳支付选择页)
        builder.button(text="🚀 1个月", callback_data="prepay_multi_30_15")
        builder.button(text="🚀 3个月", callback_data="prepay_multi_90_40")
        builder.button(text="🚀 12个月", callback_data="prepay_multi_365_140")
        # 优惠码 + 充值(用真实 callback 名)
        builder.button(text="🎟 优惠码", callback_data="activate_promo")
        builder.button(text="💳 充值", callback_data="top_up_menu")
        builder.adjust(3, 2)
    else:
        builder.button(text="🚀 立即开通", callback_data="buy_multi")
        builder.button(text="🎟 优惠码", callback_data="activate_promo")
        builder.button(text="💳 充值", callback_data="top_up_menu")
        builder.adjust(1, 2)

    return builder.as_markup()


def help_kb(lang: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 配置教程", callback_data="help_guides")
    builder.button(text="❓ 常见问题", callback_data="help_faq")
    builder.button(text="👨‍💻 联系客服", url="https://t.me/xxedce")
    builder.adjust(1)
    return builder.as_markup()

def instruction_links_kb():
    """Клавиатура только со ссылками на инструкции (без кнопки Назад)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🍏 iOS / macOS", url="https://apps.apple.com/app/shadowrocket/id932747118")
    builder.button(text="🤖 Android", url="https://github.com/2dust/v2rayNG/releases/latest")
    builder.button(text="💻 Windows", url="https://github.com/2dust/v2rayN/releases/latest")
    builder.adjust(1)
    return builder

def guides_kb(lang: str, back_callback: str = "help_main"):
    builder = instruction_links_kb()
    builder.button(text=get_text(lang, "btn_back"), callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()

def admin_main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 用户管理", callback_data="admin_users")
    builder.button(text="✉️ 群发消息", callback_data="admin_broadcast")
    builder.button(text="🎟 优惠码", callback_data="admin_promos")
    builder.button(text="📊 统计数据", callback_data="admin_stats_full")
    builder.adjust(2)
    return builder.as_markup()

def admin_back_kb(callback_data: str = "admin_home"):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 返回", callback_data=callback_data)
    return builder.as_markup()

def admin_user_action_kb(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 充值余额", callback_data=f"admin_add_balance_{user_id}")
    builder.button(text="🎁 赠送订阅", callback_data=f"admin_give_sub_{user_id}")
    builder.button(text="🔙 返回", callback_data="admin_users")
    builder.adjust(2)
    return builder.as_markup()

def admin_promo_type_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 余额充值", callback_data="create_promo_balance")
    builder.button(text="🗓 天数兑换", callback_data="create_promo_days")
    builder.button(text="🔙 返回", callback_data="admin_promos")
    builder.adjust(1)
    return builder.as_markup()

def admin_promos_main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ 创建优惠码", callback_data="admin_promo_create_start")
    builder.button(text="📜 查看列表", callback_data="admin_promo_list")
    builder.button(text="🔙 返回", callback_data="admin_home")
    builder.adjust(1)
    return builder.as_markup()

def admin_promos_list_kb(promos):
    builder = InlineKeyboardBuilder()
    for promo in promos:
        # Показываем Код | Использовано/Лимит
        uses = f"{promo.current_uses}/{promo.max_uses if promo.max_uses > 0 else '∞'}"
        builder.button(text=f"🎟 {promo.code} ({uses})", callback_data=f"admin_promo_view_{promo.id}")
    builder.button(text="🔙 返回", callback_data="admin_promos")
    builder.adjust(1)
    return builder.as_markup()

def admin_promo_view_kb(promo_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 删除", callback_data=f"admin_promo_delete_{promo_id}")
    builder.button(text="🔙 返回", callback_data="admin_promo_list")
    builder.adjust(1)
    return builder.as_markup()

def promo_sub_select_kb(subs, lang: str = "ru"):
    builder = InlineKeyboardBuilder()
    for sub in subs:
        # 将位置代码映射为显示名称
        loc_code = sub.server.location.lower()
        if loc_code == "multi":
            # 从翻译中获取名称
            loc_name = get_text(lang, "btn_multi").split("(")[0].strip()
        else:
            loc_name = get_text(lang, loc_code)
            
        label = f"{loc_name} | ⏳ {sub.expires_at.strftime('%d.%m')}"
        builder.button(text=label, callback_data=f"select_promo_sub_{sub.id}")
    builder.adjust(1)
    return builder.as_markup()