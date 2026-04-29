import hashlib
import base64
import json
import requests as _requests
import os
from src.config import settings


class CryptomusPayment:
    def __init__(self):
        self.merchant_id = settings.CRYPTOMUS_MERCHANT_ID
        self.api_key = settings.CRYPTOMUS_API_KEY
        self.base_url = "https://api.cryptomus.com/v1"

    def _sign(self, data_str: str) -> str:
        return hashlib.md5(
            (base64.b64encode(data_str.encode("utf-8")).decode("utf-8") + self.api_key).encode("utf-8")
        ).hexdigest()

    def _post(self, endpoint: str, data: dict) -> dict:
        data_str = json.dumps(data, separators=(",", ":"))
        sign = self._sign(data_str)
        headers = {
            "merchant": self.merchant_id,
            "sign": sign,
            "Content-Type": "application/json"
        }
        r = _requests.post(f"{self.base_url}/{endpoint}", headers=headers, data=data_str)
        return r.json()

    async def create_invoice(self, amount: float, currency: str, order_id: str, user_id: int) -> dict:
        import asyncio
        loop = asyncio.get_event_loop()
        data = {
            "amount": str(amount),
            "currency": currency,
            "order_id": order_id,
            "url_callback": os.getenv("CRYPTOMUS_CALLBACK_URL", "https://your-domain.com/payment/callback"),
            "lifetime": 3600,
        }
        return await loop.run_in_executor(None, lambda: self._post("payment", data))

    async def check_payment(self, order_id: str) -> dict:
        import asyncio
        loop = asyncio.get_event_loop()
        data = {"order_id": order_id}
        return await loop.run_in_executor(None, lambda: self._post("payment/info", data))


payment = CryptomusPayment()
