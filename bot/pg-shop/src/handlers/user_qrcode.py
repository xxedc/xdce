from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.database.requests import get_user_subscriptions
from datetime import datetime
import io

router = Router()

async def get_user_links(user_id: int):
    from src.services.marzban_api import api as _api
    import aiohttp
    subs = await get_user_subscriptions(user_id)
    now = datetime.now()
    active = [s for s in subs if s.expires_at > now]
    if not active:
        return [], ""

    sub_url = ""
    links = []
    try:
        mn = active[0].marzban_username
        headers = await _api._headers()
        async with aiohttp.ClientSession() as sess:
            async with sess.get(_api.host + "/api/user/" + mn, headers=headers) as r:
                if r.status == 200:
                    d = await r.json()
                    sub_url = d.get("subscription_url", "")
                    if sub_url and not sub_url.startswith("http"):
                        sub_url = _api.host + sub_url
                    links = d.get("links", [])
    except Exception:
        for s in active:
            if hasattr(s, "subscription_url") and s.subscription_url:
                sub_url = s.subscription_url
    return links, sub_url


def make_qr_bytes(content: str) -> bytes:
    import qrcode
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4
    )
    qr.add_data(content)
    qr.make(fit=True)
    try:
        from qrcode.image.styledpil import StyledPilImage
        from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
        img = qr.make_image(image_factory=StyledPilImage, module_drawer=RoundedModuleDrawer())
    except Exception:
        img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_protocol_label(link: str) -> str:
    if "REALITY" in link or ("vless://" in link and "reality" in link.lower()):
        return "VLESS Reality"
    elif "vless://" in link and "grpc" in link.lower():
        return "VLESS gRPC"
    elif "vless://" in link and "ws" in link.lower():
        return "VLESS WS"
    elif "vless://" in link and "httpupgrade" in link.lower():
        return "VLESS HTTP"
    elif "vless://" in link:
        return "VLESS"
    elif "vmess://" in link and "grpc" in link.lower():
        return "VMess gRPC"
    elif "vmess://" in link and "ws" in link.lower():
        return "VMess WS"
    elif "vmess://" in link and "httpupgrade" in link.lower():
        return "VMess HTTP"
    elif "vmess://" in link:
        return "VMess"
    elif "trojan://" in link and "grpc" in link.lower():
        return "Trojan gRPC"
    elif "trojan://" in link and "ws" in link.lower():
        return "Trojan WS"
    elif "trojan://" in link:
        return "Trojan"
    elif "ss://" in link or "shadowsocks://" in link:
        return "Shadowsocks"
    return "节点"


@router.callback_query(F.data == "show_qrcode")
async def show_qrcode_menu(callback: CallbackQuery, t, lang):
    user_id = callback.from_user.id
    links, sub_url = await get_user_links(user_id)

    if not links and not sub_url:
        await callback.answer("❌ 暂无活跃订阅", show_alert=True)
        return

    builder = InlineKeyboardBuilder()

    # 为每个协议加按钮
    for i, link in enumerate(links[:10]):  # 最多显示10个
        label = get_protocol_label(link)
        builder.button(text="📱 " + label, callback_data="qr_node_" + str(i))
    
    builder.button(text="🔙 返回账户", callback_data="back_to_profile")
    builder.adjust(1)

    text = (
        "📱 <b>选择要生成二维码的节点</b>\n\n"
        "共 " + str(len(links)) + " 个节点可用\n\n"
        "💡 <b>推荐：直接复制订阅链接导入全部协议</b>\n"
    )
    if sub_url:
        text += "<code>" + sub_url + "</code>"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qr_node_"))
async def show_node_qrcode(callback: CallbackQuery, t, lang):
    idx = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    links, sub_url = await get_user_links(user_id)

    if idx >= len(links):
        await callback.answer("❌ 节点不存在", show_alert=True)
        return

    link = links[idx]
    label = get_protocol_label(link)

    await callback.answer("🔄 生成中...")

    qr_bytes = make_qr_bytes(link)

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 返回节点列表", callback_data="show_qrcode")
    builder.adjust(1)

    caption = (
        "📱 <b>" + label + " 节点二维码</b>\n\n"
        "🍏 Shadowrocket：首页右上角扫码\n"
        "🤖 v2rayNG：右上角＋→从二维码导入\n\n"
        "🔗 节点链接：\n"
        "<code>" + link + "</code>"
    )

    await callback.message.answer_photo(
        photo=BufferedInputFile(qr_bytes, filename="qrcode.png"),
        caption=caption,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
