from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.utils.translations import get_text
from src.keyboards.builders import help_kb, guides_kb

router = Router()

@router.message(F.text.in_(["🆘 帮助中心", "🆘 帮助", get_text("ru", "help_btn")]))
async def help_menu(message: Message, t, lang):
    text = (
        "🆘 <b>帮助中心</b>\n\n"
        "━━━━━━━━━━━━\n\n"
        "📚 <b>配置教程</b>\n"
        "下载与配置指南\n\n"
        "❓ <b>常见问题</b>\n"
        "连接 / 设备 / 续期\n\n"
        "👨‍💻 <b>联系客服</b>\n"
        "在线人工支持\n\n"
        "━━━━━━━━━━━━\n\n"
        "请选择一个分类"
    )
    await message.answer(text, reply_markup=help_kb(lang), parse_mode="HTML")

@router.callback_query(F.data == "help_main")
async def back_to_help(callback: CallbackQuery, t, lang):
    await callback.message.edit_text(
        t("help_text"),
        reply_markup=help_kb(lang),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "help_faq")
async def show_faq(callback: CallbackQuery, t, lang):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_back"), callback_data="help_main")
    
    faq_text = (
        "❓ <b>常见问题</b>\n\n"
        "━━━━━━━━━━━━\n\n"
        "【连接速度】\n"
        "受网络环境影响，速度可能波动\n"
        "建议切换节点或选择低延迟线路\n\n"
        "━━━━━━━━━━━━\n\n"
        "【设备数量】\n"
        "当前套餐最多支持 5 台设备同时在线\n\n"
        "━━━━━━━━━━━━\n\n"
        "【订阅续期】\n"
        "订阅到期后将无法使用服务\n"
        "可通过购买套餐或使用优惠码续期\n\n"
        "━━━━━━━━━━━━\n\n"
        "【使用说明】\n"
        "本服务为网络加速工具\n"
        "请遵守当地法律法规合理使用\n\n"
        "━━━━━━━━━━━━"
    )
    await callback.message.edit_text(faq_text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("help_guides"))
async def show_guides(callback: CallbackQuery, t, lang):
    # Если в data есть метка from_profile, то кнопка назад должна вести в профиль
    back_cb = "back_to_profile" if "from_profile" in callback.data else "help_main"
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🍏 iOS / macOS", url="https://apps.apple.com/app/shadowrocket/id932747118")
    builder.button(text="🤖 Android", url="https://github.com/2dust/v2rayNG/releases/latest")
    builder.button(text="💻 Windows", url="https://github.com/2dust/v2rayN/releases/latest")
    builder.button(text="👨‍💻 联系客服", url="https://t.me/xxedce")
    builder.button(text="🔙 返回", callback_data=back_cb)
    builder.adjust(1)

    text = (
        "📚 <b>配置教程</b>\n\n"
        "━━━━━━━━━━━━\n\n"
        "选择设备并安装客户端\n\n"
        "🍏 <b>iOS / macOS</b>\n"
        "Shadowrocket / V2Box / Stash / ClashX\n\n"
        "🤖 <b>Android</b>\n"
        "v2rayNG / Clash / Clash Meta / SagerNet\n\n"
        "💻 <b>Windows</b>\n"
        "v2rayN / Clash Verge / Nekoray\n\n"
        "🐧 <b>Linux</b>\n"
        "Clash / Clash Verge / v2ray-core\n\n"
        "━━━━━━━━━━━━\n\n"
        "📥 <b>使用方法</b>\n\n"
        "1. 打开客户端\n"
        "2. 添加订阅\n"
        "3. 粘贴订阅链接\n"
        "4. 更新并连接\n\n"
        "━━━━━━━━━━━━\n\n"
        "⚠️ <b>Clash Meta 用户注意</b>\n\n"
        "部分版本不支持 VLESS Reality\n"
        "推荐选择以下节点：\n"
        "🎬 DC · 流媒体（Trojan WS）\n"
        "🌐 DC · 稳定（VMess WS）\n"
        "🔒 DC · 兼容（Shadowsocks）\n\n"
        "━━━━━━━━━━━━\n\n"
        "💡 推荐新手：Shadowrocket / v2rayNG\n"
        "📌 订阅链接在「我的订阅」中获取"
    )
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")