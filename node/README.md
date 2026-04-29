# PasarGuard 节点部署指南

## 前置条件

- Ubuntu 22.04+ 服务器(可与面板分开)
- 已部署好的 PasarGuard 面板

## 部署步骤

### 1. 安装 Docker

```bash
curl -fsSL https://get.docker.com | bash
systemctl enable --now docker
```

### 2. 创建目录

```bash
mkdir -p /opt/pg-node
mkdir -p /var/lib/pg-node/certs
cd /opt/pg-node
```

### 3. 复制配置

```bash
cp /tmp/xdce/node/docker-compose.yml ./docker-compose.yml
cp /tmp/xdce/node/.env.example ./.env
```

### 4. 在面板添加节点(获取证书 + API Key)

1. 浏览器打开面板 → 节点管理 → 添加节点
2. 填写:
   - 名称:任意,如 `日本节点`
   - 地址:本节点服务器公网 IP
   - API 端口:`62050`
   - 服务端口:`62051`
3. 点击"生成证书",得到:
   - **SSL 证书**(粘贴到 `ssl_cert.pem`)
   - **SSL 密钥**(粘贴到 `ssl_key.pem`)
   - **API Key**(UUID,粘贴到 .env)

### 5. 把证书写到本地

```bash
nano /var/lib/pg-node/certs/ssl_cert.pem
```

粘贴 SSL 证书,保存退出。

```bash
nano /var/lib/pg-node/certs/ssl_key.pem
```

粘贴 SSL 密钥,保存退出。

### 6. 编辑 .env

```bash
nano /opt/pg-node/.env
```

修改 3 行:

```
SSL_CERT_FILE=/var/lib/pg-node/certs/ssl_cert.pem
SSL_KEY_FILE=/var/lib/pg-node/certs/ssl_key.pem
API_KEY=面板返回的UUID
```

### 7. 启动节点

```bash
docker compose up -d
```

### 8. 防火墙

```bash
ufw allow 62050/tcp
ufw allow 62051/tcp
ufw allow 443/tcp
ufw allow 8443/tcp
```

### 9. 验证

回到面板 → 节点管理,本节点状态应变成"已连接"(绿色)。

---

## 多节点部署

每台节点服务器重复上面 1-9 步骤。每个节点在面板里**独立添加**,得到不同的 API Key 和证书。

---

## 常用命令

### 查看日志

```bash
cd /opt/pg-node
docker compose logs -f
```

### 重启

```bash
docker compose restart
```

### 升级

```bash
docker compose pull
docker compose up -d
```

---

## 故障排查

### 节点显示"未连接"

```bash
# 检查防火墙
ufw status

# 检查 docker
docker ps | grep node

# 检查日志
cd /opt/pg-node
docker compose logs --tail 50

# 从面板服务器测试 API 端口
curl https://节点IP:62050
```

### 证书错误

证书必须以 `-----BEGIN CERTIFICATE-----` 开头,密钥以 `-----BEGIN PRIVATE KEY-----` 开头,不要有多余空行。

---

## 下一步

节点装好后,装 bot:[../bot/README.md](../bot/README.md)
