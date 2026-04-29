# PasarGuard 面板部署

## 前置
- Ubuntu 22.04+
- 域名解析到本机

## 步骤

1. 装 Docker:
   curl -fsSL https://get.docker.com | bash
   apt install -y nginx certbot python3-certbot-nginx

2. 复制配置:
   mkdir -p /opt/pasarguard && cd /opt/pasarguard
   cp /path/to/xdce/panel/docker-compose.yml ./
   cp /path/to/xdce/panel/.env.example ./.env
   nano .env  # 改域名

3. 启动:
   docker compose up -d

4. 创建管理员:
   docker exec -it pasarguard-pasarguard-1 pasarguard cli admin create --sudo

5. SSL + Nginx:
   certbot --nginx -d your-domain.com
   cp /path/to/xdce/panel/nginx.conf.example /etc/nginx/sites-available/pasarguard
   sed -i "s|your-panel-domain.com|你的域名|g" /etc/nginx/sites-available/pasarguard
   ln -sf /etc/nginx/sites-available/pasarguard /etc/nginx/sites-enabled/
   systemctl reload nginx

## 升级
   cd /opt/pasarguard && docker compose pull && docker compose up -d
