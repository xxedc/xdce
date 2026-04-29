# PasarGuard 节点部署

## 前置
- 已装好的面板

## 步骤

1. 装 Docker:
   curl -fsSL https://get.docker.com | bash

2. 创建目录:
   mkdir -p /opt/pg-node /var/lib/pg-node/certs
   cd /opt/pg-node
   cp /path/to/xdce/node/docker-compose.yml ./
   cp /path/to/xdce/node/.env.example ./.env

3. 面板里添加节点(获取证书+API Key)
   把证书贴到 /var/lib/pg-node/certs/ssl_cert.pem 和 ssl_key.pem
   nano .env  # 填 API_KEY

4. 启动:
   docker compose up -d

5. 防火墙:
   ufw allow 62050/tcp
   ufw allow 62051/tcp

## 多节点
每台节点重复上面步骤即可。

## 升级
   cd /opt/pg-node && docker compose pull && docker compose up -d
