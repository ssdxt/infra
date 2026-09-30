import time
import hmac
import hashlib
import base64

import httpx
import urllib.parse

# timestamp = str(round(time.time() * 1000))
# secret = 'this is secret'
# secret_enc = secret.encode('utf-8')
# string_to_sign = '{}\n{}'.format(timestamp, secret)
# string_to_sign_enc = string_to_sign.encode('utf-8')
# hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
# sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))


class DingTalkClient:
    def __init__(self, webhook, secret):
        self.url = webhook
        self.secret = secret
        self.headers = {
            'Content-Type': 'application/json'
        }

    def gen_sign(self, timestamp: str) -> str:
        # 拼接timestamp和secret
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = '{}\n{}'.format(timestamp, self.secret)
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return sign

    async def send_markdown_msg(self, title, msg: str):
        timestamp = str(round(time.time() * 1000))
        sign = self.gen_sign(timestamp)

        url = f"{self.url}&timestamp={timestamp}&sign={sign}"

        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": msg,
            }
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self.headers, json=data)
            result = resp.json()
            return result.get("code") == 200