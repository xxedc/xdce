import os
import aiohttp
from datetime import datetime, timezone
from src.config import settings


class MarzbanAPI:
    """适配 PasarGuard 的 API 客户端(类名保留以兼容旧引用)"""

    def __init__(self):
        self.host = settings.MARZBAN_HOST
        self.username = settings.MARZBAN_USERNAME
        self.password = settings.MARZBAN_PASSWORD
        # 默认 group_ids,可通过环境变量 PG_GROUP_IDS=2,3 覆盖
        env_groups = os.getenv("PG_GROUP_IDS", "2")
        self.default_group_ids = [int(x.strip()) for x in env_groups.split(",") if x.strip()]

    async def _get_token(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.host}/api/admin/token",
                data={"username": self.username, "password": self.password},
            ) as resp:
                data = await resp.json()
                return data["access_token"]

    async def _headers(self):
        token = await self._get_token()
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _format_expire(expire_timestamp: int):
        """unix timestamp → PasarGuard 要求的 ISO 8601 UTC 字符串;0 或负数 → None"""
        if not expire_timestamp or expire_timestamp <= 0:
            return None
        return (
            datetime.fromtimestamp(expire_timestamp, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    async def create_key(self, username: str, expire_timestamp: int = 0, data_limit_gb: int = 0) -> tuple:
        """创建或更新用户。返回 (vless_key, sub_url)。
        PasarGuard 不再返回 links 字段,vless_key 暂返回空,主要使用 sub_url 订阅链接。
        """
        headers = await self._headers()
        data_limit_bytes = data_limit_gb * 1024**3 if data_limit_gb > 0 else 0
        expire_iso = self._format_expire(expire_timestamp)

        payload = {
            "username": username,
            "proxy_settings": {
                "vless": {"flow": "xtls-rprx-vision"},
                "vmess": {},
                "trojan": {},
                "shadowsocks": {"method": "chacha20-ietf-poly1305"},
            },
            "group_ids": self.default_group_ids,
            "expire": expire_iso,
            "data_limit": data_limit_bytes,
            "data_limit_reset_strategy": "month" if data_limit_gb > 0 else "no_reset",
            "status": "active",
        }

        async with aiohttp.ClientSession() as session:
            # 先查是否已存在
            async with session.get(
                f"{self.host}/api/user/{username}", headers=headers
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    # 已存在 → 续费/调流量
                    update_payload = {
                        "expire": expire_iso,
                        "data_limit": data_limit_bytes,
                        "data_limit_reset_strategy": "month" if data_limit_gb > 0 else "no_reset",
                        "status": "active",
                    }
                    async with session.put(
                        f"{self.host}/api/user/{username}",
                        json=update_payload,
                        headers=headers,
                    ) as ur:
                        if ur.status == 200:
                            data = await ur.json()
                else:
                    # 不存在 → 创建
                    async with session.post(
                        f"{self.host}/api/user", json=payload, headers=headers
                    ) as resp:
                        data = await resp.json()

        vless_key = ""  # PasarGuard 不返回 links,留空
        sub_url = data.get("subscription_url", "")
        if sub_url and not sub_url.startswith("http"):
            sub_url = self.host + sub_url

        return vless_key, sub_url

    async def update_user_expire(self, username: str, expire_timestamp: int, data_limit_gb: int = 0):
        headers = await self._headers()
        data_limit_bytes = data_limit_gb * 1024**3 if data_limit_gb > 0 else 0
        expire_iso = self._format_expire(expire_timestamp)
        payload = {
            "expire": expire_iso,
            "data_limit": data_limit_bytes,
            "data_limit_reset_strategy": "month" if data_limit_gb > 0 else "no_reset",
            "status": "active",
        }
        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{self.host}/api/user/{username}", json=payload, headers=headers
            ) as r:
                return await r.json()

    async def get_subscription_url(self, username: str) -> str:
        try:
            headers = await self._headers()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.host}/api/user/{username}", headers=headers
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        sub_url = data.get("subscription_url", "")
                        if sub_url and not sub_url.startswith("http"):
                            sub_url = self.host + sub_url
                        return sub_url
        except Exception:
            pass
        return ""

    async def get_user_status(self, username: str) -> dict:
        try:
            headers = await self._headers()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.host}/api/user/{username}", headers=headers
                ) as resp:
                    data = await resp.json()
                    return {"online": 1 if data.get("online_at") else 0}
        except Exception:
            return {"online": 0}

    async def get_user_usage(self, username: str) -> int:
        try:
            headers = await self._headers()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.host}/api/user/{username}", headers=headers
                ) as resp:
                    data = await resp.json()
                    return data.get("used_traffic", 0)
        except Exception:
            return 0


    async def list_users_by_prefix(self, prefix: str = "trial_") -> list:
        """列出所有用户名以 prefix 开头的用户"""
        try:
            headers = await self._headers()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.host}/api/users?limit=500",
                    headers=headers,
                ) as r:
                    data = await r.json()
                    all_users = data.get("users", [])
                    return [u for u in all_users if u.get("username","").startswith(prefix)]
        except Exception:
            return []

    async def delete_user(self, username: str) -> bool:
        """删除用户"""
        try:
            headers = await self._headers()
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.host}/api/user/{username}",
                    headers=headers,
                ) as r:
                    return r.status in (200, 204)
        except Exception:
            return False

    async def cleanup_expired_trials(self, prefix: str = "trial_") -> int:
        """删除所有已过期的 trial 账号,返回删除的数量"""
        import time as _time
        users = await self.list_users_by_prefix(prefix)
        now = int(_time.time())
        deleted = 0
        for u in users:
            username = u.get("username", "")
            if not username.startswith(prefix):
                continue
            expire = u.get("expire")
            is_expired = False
            if isinstance(expire, str):
                try:
                    from datetime import datetime
                    e = datetime.fromisoformat(expire.replace("Z", "+00:00"))
                    is_expired = e.timestamp() <= now
                except Exception:
                    is_expired = False
            elif isinstance(expire, (int, float)):
                is_expired = expire and expire <= now
            if u.get("status") in ("expired", "limited", "disabled"):
                is_expired = True
            if is_expired:
                ok = await self.delete_user(username)
                if ok:
                    deleted += 1
        return deleted



    async def add_data_limit_gb(self, username: str, gb_to_add: float) -> bool:
        """给用户的 data_limit 增加 N GB(保留原有到期时间和其他设置)"""
        if gb_to_add <= 0:
            return False
        try:
            headers = await self._headers()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.host}/api/user/{username}", headers=headers
                ) as r:
                    if r.status != 200:
                        return False
                    user_data = await r.json()
                current_limit = user_data.get("data_limit") or 0
                new_limit = int(current_limit + gb_to_add * 1024**3)
                payload = {"data_limit": new_limit}
                async with session.put(
                    f"{self.host}/api/user/{username}",
                    json=payload, headers=headers
                ) as r2:
                    return r2.status in (200, 204)
        except Exception:
            return False

    async def add_expire_days(self, username: str, days_to_add: int) -> bool:
        """给用户延长 N 天到期时间"""
        if days_to_add <= 0:
            return False
        try:
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            headers = await self._headers()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.host}/api/user/{username}", headers=headers
                ) as r:
                    if r.status != 200:
                        return False
                    user_data = await r.json()
                current_expire = user_data.get("expire")
                base_dt = None
                if current_expire:
                    if isinstance(current_expire, str):
                        try:
                            base_dt = _dt.fromisoformat(current_expire.replace("Z", "+00:00"))
                        except Exception:
                            base_dt = _dt.now(_tz.utc)
                    elif isinstance(current_expire, (int, float)):
                        base_dt = _dt.fromtimestamp(current_expire, tz=_tz.utc)
                if not base_dt or base_dt < _dt.now(_tz.utc):
                    base_dt = _dt.now(_tz.utc)
                new_expire = (base_dt + _td(days=days_to_add)).isoformat().replace("+00:00", "Z")
                payload = {"expire": new_expire}
                async with session.put(
                    f"{self.host}/api/user/{username}",
                    json=payload, headers=headers
                ) as r2:
                    return r2.status in (200, 204)
        except Exception:
            return False


api = MarzbanAPI()
