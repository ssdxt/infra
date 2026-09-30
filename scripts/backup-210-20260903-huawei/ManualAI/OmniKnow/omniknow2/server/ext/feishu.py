import hashlib
import base64
import hmac
import time

import httpx

from utils.log import logger


class FeishuClient:
    def __init__(self, webhook, secret):
        self.url = webhook
        self.secret = secret
        self.headers = {
            'Content-Type': 'application/json'
        }

    def gen_sign(self, timestamp: int) -> str:
        # 拼接timestamp和secret
        string_to_sign = '{}\n{}'.format(timestamp, self.secret)
        hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        # 对结果进行base64处理
        sign = base64.b64encode(hmac_code).decode('utf-8')
        return sign

    async def send_plain_text_msg(self, msg: str):
        timestamp = int(time.time())
        sign = self.gen_sign(timestamp)

        data = {
            'timestamp': timestamp,
            'sign': sign,
            'msg_type': 'text',
            'content': {
                'text': msg
            }
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(self.url, headers=self.headers, json=data)
            result = resp.json()
            return result.get("code") == 200

    async def send_card_msg(self, title, message, platform_url):
        timestamp = int(time.time())
        sign = self.gen_sign(timestamp)

        error_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        data = {
            'timestamp': timestamp,
            'sign': sign,
            'msg_type': 'interactive',
            'card': {
                "schema": "2.0",
                "config": {
                    "update_multi": True,
                    "style": {
                        "text_size": {
                            "normal_v2": {
                                "default": "normal",
                                "pc": "normal",
                                "mobile": "heading"
                            }
                        }
                    }
                },
                "body": {
                    "direction": "vertical",
                    "padding": "12px 12px 12px 12px",
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": message,
                            "text_align": "left",
                            "text_size": "normal_v2",
                            "margin": "0px 0px 0px 0px"
                        },
                        {
                            "tag": "hr",
                            "margin": "0px 0px 0px 0px"
                        },
                        {
                            "tag": "column_set",
                            "horizontal_spacing": "8px",
                            "horizontal_align": "left",
                            "columns": [
                                {
                                    "tag": "column",
                                    "width": "weighted",
                                    "elements": [
                                        {
                                            "tag": "button",
                                            "text": {
                                                "tag": "plain_text",
                                                "content": "打开平台查看详情"
                                            },
                                            "type": "primary_filled",
                                            "width": "default",
                                            "size": "medium",
                                            "icon": {
                                                "tag": "standard_icon",
                                                "token": "lookup_outlined"
                                            },
                                            "behaviors": [
                                                {
                                                    "type": "open_url",
                                                    "default_url": f"{platform_url}",
                                                    "pc_url": "",
                                                    "ios_url": "",
                                                    "android_url": ""
                                                }
                                            ],
                                            "margin": "0px 0px 0px 0px"
                                        }
                                    ],
                                    "vertical_spacing": "8px",
                                    "horizontal_align": "left",
                                    "vertical_align": "top",
                                    "weight": 1
                                }
                            ],
                            "margin": "0px 0px 0px 0px"
                        }
                    ]
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title
                    },
                    "subtitle": {
                        "tag": "plain_text",
                        "content": error_time
                    },
                    "template": "blue",
                    "padding": "12px 12px 12px 12px"
                }
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.url, headers=self.headers, json=data)
            response = resp.json()
            if response.get("code") == 0:
                return True
            else:
                logger.info(f"飞书通知发送失败：{response}")
                return False
