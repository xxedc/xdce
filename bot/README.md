# Telegram 商店机器人

## 功能
- 试用/购买/续费
- Cryptomus 加密支付
- 每日签到/分享/入群奖励
- 自动推广(每日随机时间)
- 试用→永久自动升级

## 前置
- 已装好的面板
- Bot Token(从 @BotFather)

## 步骤

1. 依赖:
   apt install -y python3 python3-pip git fonts-noto-cjk

2. 克隆:
   git clone https://github.com/xxedc/xdce.git /tmp/xdce
   cp -r /tmp/xdce/bot/pg-shop /opt/pg-shop
   cd /opt/pg-shop
   pip3 install -r requirements.txt --break-system-packages
   pip3 install Pillow pytz aiosqlite --break-system-packages

3. 配置:
   cp /tmp/xdce/bot/.env.example /opt/pg-shop/.env
   nano /opt/pg-shop/.env

   必填:
   - BOT_TOKEN(从 @BotFather)
   - ADMIN_IDS(你的 Telegram ID)
   - MARZBAN_HOST(面板地址)
   - MARZBAN_USERNAME=admin
   - MARZBAN_PASSWORD(面板密码)

4. systemd:
   cp /opt/pg-shop/pg-shop.service.example /etc/systemd/system/pg-shop.service
   systemctl daemon-reload
   systemctl enable --now pg-shop

5. 验证:
   journalctl -u pg-shop -f

## 推广图
   cd /opt/pg-shop && python3 gen_promo.py

## 故障排查
   journalctl -u pg-shop -f
   systemctl restart pg-shop
