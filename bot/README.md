# Telegram 商店机器人部署指南

## 功能特性

- 🎁 用户注册 / 免费试用 / 购买订阅
- 💰 余额充值(Cryptomus 加密货币支付)
- 📅 每日签到(+2GB / 月上限 50GB)
- 👥 邀请返利 / 分享奖励(+1GB / 每天 2 次)
- 🎉 入群领奖(+20GB +7天)
- 📢 自动推广(每日随机时段发送宣传图)
- 🚀 试用 → 永久号自动升级(累积奖励一起迁移)
- 📊 管理员后台统计(节点状态自动检测国家)

## 前置条件

- Ubuntu 22.04+ 服务器
- 已部署的 PasarGuard 面板
- Telegram Bot Token(从 [@BotFather](https://t.me/BotFather) 创建)
- Cryptomus 商户账号(可选,加密支付才需要)

## 部署步骤

### 1. 安装系统依赖

```bash
apt update
apt install -y python3 python3-pip git fonts-noto-cjk
```

### 2. 克隆仓库 + 复制代码

```bash
git clone https://github.com/xxedc/xdce.git /tmp/xdce
cp -r /tmp/xdce/bot/pg-shop /opt/pg-shop
cd /opt/pg-shop
```

### 3. 安装 Python 包

```bash
pip3 install -r requirements.txt --break-system-packages
pip3 install Pillow pytz aiosqlite --break-system-packages
```

### 4. 配置 .env

```bash
cp /tmp/xdce/bot/.env.example /opt/pg-shop/.env
nano /opt/pg-shop/.env
```

**必填字段**:

| 变量 | 说明 | 示例 |
|---|---|---|
| `BOT_TOKEN` | @BotFather 创建的 token | `1234567890:ABC...` |
| `ADMIN_IDS` | 管理员 Telegram ID(逗号分隔) | `123456789` |
| `MARZBAN_HOST` | 面板地址 | `https://panel.example.com` |
| `MARZBAN_USERNAME` | 面板管理员用户名 | `admin` |
| `MARZBAN_PASSWORD` | 面板管理员密码 | `your_password` |

**可选字段**(加密支付):

| 变量 | 说明 |
|---|---|
| `CRYPTOMUS_MERCHANT_ID` | Cryptomus 商户 ID |
| `CRYPTOMUS_API_KEY` | Cryptomus API Key |
| `CRYPTOMUS_CALLBACK_URL` | 支付回调 URL |

### 5. 配置 systemd

```bash
cp /opt/pg-shop/pg-shop.service.example /etc/systemd/system/pg-shop.service
systemctl daemon-reload
systemctl enable --now pg-shop
```

### 6. 验证

```bash
systemctl status pg-shop
journalctl -u pg-shop -f
```

应该看到启动成功日志。

### 7. Telegram 测试

打开 Telegram,搜索你的 bot,点击 `/start`,应该看到主菜单。

---

## 推广图片生成

```bash
cd /opt/pg-shop
python3 gen_promo.py
```

会在 `promo_images/` 生成 12 张主题宣传图。

---

## 常用命令

```bash
# 实时日志
journalctl -u pg-shop -f

# 重启
systemctl restart pg-shop

# 状态
systemctl status pg-shop

# 停止
systemctl stop pg-shop
```

---

## 升级 bot

```bash
cd /tmp
rm -rf xdce
git clone https://github.com/xxedc/xdce.git xdce
cp -r xdce/bot/pg-shop/src/* /opt/pg-shop/src/
systemctl restart pg-shop
```

⚠️ **不要覆盖** `.env` 和 `shop.db`(数据库)!

---

## 故障排查

### bot 启动失败

```bash
cd /opt/pg-shop
python3 main.py 2>&1 | head -30
```

常见错误:
- `BOT_TOKEN invalid` → .env 里 token 写错
- `Connection refused` → 面板地址不对
- `ImportError` → Python 包没装全

### 数据库报错

```bash
cp /opt/pg-shop/shop.db /opt/pg-shop/shop.db.bak
rm /opt/pg-shop/shop.db
systemctl restart pg-shop
```

数据库会自动重建。

---

## Cryptomus 支付配置

1. 注册 https://app.cryptomus.com
2. 创建商户 → 拿到 `MERCHANT_ID`
3. API → Generate Key → 拿到 `API_KEY`
4. 配置回调 URL:`https://你的域名/payment/callback`
5. 把 IP 加入 Cryptomus 白名单
6. .env 填上 token,`systemctl restart pg-shop`

---

## License

MIT
