"""DC加速 - 12 套宣传图生成"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

OUTPUT_DIR = "/opt/pg-shop/promo_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)
W, H = 1920, 1080

SLOTS = [
    {"key": "01_global", "tagline": "GLOBAL  ·  UNLIMITED",
     "title": "畅 联 全 球  ·  一 键 解 锁",
     "lines": ["全 球 优 选 节 点", "5 设 备 同 时 在 线", "月 套 餐  ¥ 15 起"],
     "g1": (255, 175, 123), "g2": (255, 145, 96), "g3": (255, 217, 158)},
    {"key": "02_bandwidth", "tagline": "DEDICATED  ·  BANDWIDTH",
     "title": "独 享 带 宽  ·  满 速 到 家",
     "lines": ["千 兆 独 享 不 共 享", "晚 高 峰 不 限 速", "低 延 迟 · 零 拥 堵"],
     "g1": (139, 195, 145), "g2": (96, 154, 116), "g3": (180, 217, 175)},
    {"key": "03_dedicated", "tagline": "PRIVATE LINE  ·  EXPRESS",
     "title": "专 线 加 速  ·  告 别 拥 堵",
     "lines": ["IPLC 国 际 专 线", "BGP 智 能 路 由", "三 网 优 化 直 连"],
     "g1": (94, 148, 192), "g2": (52, 96, 145), "g3": (130, 178, 213)},
    {"key": "04_streaming", "tagline": "4K  ·  STREAMING",
     "title": "4 K 不 卡  ·  原 生 直 连",
     "lines": ["油 管 4K · 零 缓 冲", "B 站 港 区 · 原 生 解 锁", "TikTok · 一 键 直 通"],
     "g1": (102, 158, 178), "g2": (74, 122, 152), "g3": (147, 184, 197)},
    {"key": "05_netflix", "tagline": "STREAM  ·  UNLOCKED",
     "title": "解 锁 追 剧  ·  原 生 I P",
     "lines": ["Netflix · Disney+", "HBO · Hulu · Prime", "全 平 台 原 生 解 锁"],
     "g1": (228, 145, 138), "g2": (211, 113, 105), "g3": (244, 188, 167)},
    {"key": "06_gaming", "tagline": "GAMING  ·  LOW-LATENCY",
     "title": "原 生 I P  ·  稳 如 老 狗",
     "lines": ["游 戏 竞 技 · 直 连 原 生", "加 密 链 路 · 零 日 志", "年 卡 立 省 22%"],
     "g1": (88, 96, 145), "g2": (47, 53, 86), "g3": (120, 100, 158)},
    {"key": "07_multidevice", "tagline": "MULTI-DEVICE  ·  5-IN-1",
     "title": "一 号 通 用  ·  5 端 齐 发",
     "lines": ["手 机 · 平 板 · 电 脑", "iOS · 安 卓 · Win · Mac", "全 家 共 享 一 个 号"],
     "g1": (128, 213, 199), "g2": (90, 175, 165), "g3": (175, 230, 220)},
    {"key": "08_anticensor", "tagline": "ANTI-BLOCK  ·  STABLE",
     "title": "抗 封 锁 强  ·  稳 定 不 掉",
     "lines": ["Reality 抗 封 锁 黑 科 技", "节 点 自 动 切 换", "重 大 节 日 不 掉 线"],
     "g1": (140, 150, 165), "g2": (95, 105, 125), "g3": (175, 185, 200)},
    {"key": "09_privacy", "tagline": "PRIVACY  ·  ENCRYPTED",
     "title": "加 密 链 路  ·  零 日 志",
     "lines": ["TLS 1.3 全 程 加 密", "无 流 量 日 志", "无 用 户 信 息 留 存"],
     "g1": (88, 145, 130), "g2": (50, 100, 90), "g3": (130, 180, 165)},
    {"key": "10_monthly", "tagline": "MONTHLY  ·  STARTER",
     "title": "月 卡 ¥ 15  ·  奶 茶 钱",
     "lines": ["一 杯 奶 茶 = 一 个 月", "200GB 流 量 包 月", "新 用 户 首 月 体 验"],
     "g1": (255, 211, 105), "g2": (245, 175, 60), "g3": (255, 232, 158)},
    {"key": "11_quarterly", "tagline": "QUARTERLY  ·  SAVE 11%",
     "title": "季 卡 省 11%  ·  锁 定 低 价",
     "lines": ["3 个 月 仅 ¥ 40", "平 均 每 月 ¥ 13", "送 7 天 试 用 期"],
     "g1": (255, 158, 142), "g2": (235, 110, 95), "g3": (255, 200, 180)},
    {"key": "12_yearly", "tagline": "YEARLY  ·  SAVE 22%",
     "title": "年 卡 省 22%  ·  一 年 无 忧",
     "lines": ["全 年 ¥ 140 · 一 步 到 位", "平 均 每 月 ¥ 11.6", "VIP 优 先 客 服"],
     "g1": (158, 125, 200), "g2": (108, 75, 158), "g3": (190, 165, 220)},
]


def make_gradient(w, h, c1, c2, c3):
    img = Image.new("RGB", (w, h), c1)
    px = img.load()
    diag = w + h
    for y in range(h):
        for x in range(w):
            t = (x + y) / diag
            if t < 0.5:
                tt = t * 2
                c = tuple(int(c1[i] + (c2[i] - c1[i]) * tt) for i in range(3))
            else:
                tt = (t - 0.5) * 2
                c = tuple(int(c2[i] + (c3[i] - c2[i]) * tt) for i in range(3))
            px[x, y] = c
    return img


def add_atmosphere(img, color):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.ellipse([-400, -300, 800, 600], fill=(255, 255, 255, 35))
    d.ellipse([W - 600, H - 600, W + 200, H + 200], fill=(*color, 65))
    d.ellipse([W // 2 - 300, H - 700, W // 2 + 500, H - 100], fill=(255, 255, 255, 25))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=200))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)
    return img.convert("RGB")


def find_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_card(img, slot):
    d = ImageDraw.Draw(img, "RGBA")
    brand = find_font(72, bold=True)
    bt = "DC 加速"
    bb = d.textbbox((0, 0), bt, font=brand)
    d.text(((W - (bb[2] - bb[0])) / 2, 100), bt, font=brand, fill=(255, 255, 255, 255))

    d.rounded_rectangle([W / 2 - 40, 200, W / 2 + 40, 205], radius=2, fill=(255, 255, 255, 200))

    tag = find_font(28)
    tt = slot["tagline"]
    bb = d.textbbox((0, 0), tt, font=tag)
    d.text(((W - (bb[2] - bb[0])) / 2, 230), tt, font=tag, fill=(255, 255, 255, 220))

    title = find_font(108, bold=True)
    tt = slot["title"]
    bb = d.textbbox((0, 0), tt, font=title)
    tw = bb[2] - bb[0]
    while tw > W - 160 and title.size > 70:
        title = find_font(title.size - 4, bold=True)
        bb = d.textbbox((0, 0), tt, font=title)
        tw = bb[2] - bb[0]
    d.text(((W - tw) / 2 + 6, 360 + 6), tt, font=title, fill=(0, 0, 0, 60))
    d.text(((W - tw) / 2, 360), tt, font=title, fill=(255, 255, 255, 255))

    card_y, card_h = 600, 300
    card_x = 160
    card_w = W - 320
    d.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=44, fill=(255, 255, 255, 55))
    sec_w = card_w / 3
    line_font = find_font(40, bold=True)
    for i, line in enumerate(slot["lines"]):
        lf = line_font
        bb = d.textbbox((0, 0), line, font=lf)
        tw = bb[2] - bb[0]
        while tw > sec_w - 40 and lf.size > 26:
            lf = find_font(lf.size - 2, bold=True)
            bb = d.textbbox((0, 0), line, font=lf)
            tw = bb[2] - bb[0]
        sec_cx = card_x + sec_w * i + sec_w / 2
        d.text((sec_cx - tw / 2, card_y + card_h / 2 - 28), line, font=lf, fill=(255, 255, 255, 255))
        if i < 2:
            sx = card_x + sec_w * (i + 1)
            d.rounded_rectangle([sx - 1, card_y + 70, sx + 1, card_y + card_h - 70], radius=1, fill=(255, 255, 255, 100))

    foot = find_font(32)
    ft = "@dcxxe_bot     ·     t.me/XXEDC13"
    bb = d.textbbox((0, 0), ft, font=foot)
    d.text(((W - (bb[2] - bb[0])) / 2, 980), ft, font=foot, fill=(255, 255, 255, 220))


def generate_all():
    for s in SLOTS:
        img = make_gradient(W, H, s["g1"], s["g2"], s["g3"])
        img = add_atmosphere(img, s["g1"])
        draw_card(img, s)
        out = os.path.join(OUTPUT_DIR, f"{s['key']}.jpg")
        img.save(out, "JPEG", quality=92)
        print(f"OK {out}")


if __name__ == "__main__":
    generate_all()
    print("done")
