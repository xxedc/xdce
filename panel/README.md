# PasarGuard 面板部署指南

## 前置条件

- Ubuntu 22.04+ 服务器
- 一个解析到本服务器的域名(例如 `panel.example.com`)
- 域名 A 记录指向服务器 IP

## 部署步骤

### 1. 安装 Docker

```bash
curl -fsSL https://get.docker.com | bash
systemctl enable --now docker
```

### 2. 安装 Nginx + Certbot

```bash
apt update
apt install -y nginx certbot python3-certbot-nginx
```

### 3. 创建目录

```bash
mkdir -p /opt/pasarguard
cd /opt/pasarguard
```

### 4. 复制配置(假设已 git clone 仓库到 /tmp/xdce)

```bash
cp /tmp/xdce/panel/docker-compose.yml ./docker-compose.yml
cp /tmp/xdce/panel/.env.example ./.env
```

### 5. 编辑 .env

```bash
nano /opt/pasarguard/.env
```

主要修改:`UVICORN_HOST=panel.example.com`(改成你的域名)

### 6. 启动 PasarGuard

```bash
docker compose up -d
```

### 7. 创建管理员账号

```bash
docker exec -it pasarguard-pasarguard-1 pasarguard cli admin create --sudo
```

按提示输入用户名和密码。

### 8. 申请 SSL 证书

```bash
certbot --nginx -d panel.example.com
```

按提示同意条款,输入邮箱即可。

### 9. 配置 Nginx 反代

```bash
cp /tmp/xdce/panel/nginx.conf.example /etc/nginx/sites-available/pasarguard
sed -i 's|your-panel-domain.com|panel.example.com|g' /etc/nginx/sites-available/pasarguard
ln -sf /etc/nginx/sites-available/pasarguard /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### 10. 访问面板

浏览器打开 `https://panel.example.com`,用第 7 步创建的账号登录。

---

## 常用命令

### 查看日志

```bash
cd /opt/pasarguard
docker compose logs -f
```

### 重启面板

```bash
docker compose restart
```

### 升级到最新版

```bash
docker compose pull
docker compose up -d
```

### 停止

```bash
docker compose down
```

---

## 故障排查

### 502 Bad Gateway

```bash
docker ps | grep pasarguard
# 没运行就重启
docker compose up -d
```

### 登录失败

```bash
# 列出管理员
docker exec -it pasarguard-pasarguard-1 pasarguard cli admin list

# 重置密码
docker exec -it pasarguard-pasarguard-1 pasarguard cli admin update --username admin
```

### 证书续期

```bash
certbot renew
systemctl reload nginx
```

---

## 下一步

面板装好后,继续装节点:[../node/README.md](../node/README.md)
