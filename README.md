# xdce - VPN 服务一键部署套件

完整 VPN 自营服务方案,三件套独立部署。

## 组件

- 🛡 **PasarGuard 面板** - 用户管理 + 订阅链接生成(Docker)
- 🚀 **PasarGuard 节点** - Xray 节点服务(Docker,可多节点)
- 🤖 **Telegram 商店机器人** - 自动售卖 + 签到 + 推广(Python)

## 架构

```
面板服务器 ←→ 节点服务器(可多个)
   ↓
 bot 服务器
```

**最简部署**:三件套全装一台服务器(测试用)
**生产部署**:面板+bot 一台,节点 1+ 台分布(多地高速)

## 系统要求

| 组件 | 系统 | 内存 | 依赖 |
|---|---|---|---|
| 面板 | Ubuntu 22.04+ | 1GB+ | Docker + Nginx + Certbot |
| 节点 | Ubuntu 22.04+ | 512MB+ | Docker |
| bot | Ubuntu 22.04+ | 512MB+ | Python 3.10+ |

## 部署顺序(重要!)

1. 先部署面板 `panel/` → 创建管理员账号
2. 再部署节点 `node/` → 在面板里添加节点拿证书
3. 最后部署 bot `bot/` → 配置面板地址 + admin 凭据

## 快速开始

```bash
git clone https://github.com/xxedc/xdce.git
cd xdce
```

然后按顺序看每个目录的 README:

- 📘 [panel/README.md](panel/README.md) - 面板部署指南
- 📗 [node/README.md](node/README.md) - 节点部署指南
- 📕 [bot/README.md](bot/README.md) - 机器人部署指南

## 为什么 panel/ 和 node/ 文件少?

PasarGuard 是 **Docker 镜像**部署,你不需要下载源码 — Docker 启动时自动从 Docker Hub 拉镜像。仓库里只需要 `docker-compose.yml` + `.env.example` 配置文件。

升级只需要:

```bash
docker compose pull
docker compose up -d
```

镜像自动更新到最新版,**仓库不需要变**。

## License

MIT
