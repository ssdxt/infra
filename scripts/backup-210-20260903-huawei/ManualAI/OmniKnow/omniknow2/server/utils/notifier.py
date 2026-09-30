import asyncio
import traceback

from core.config import settings
from utils.public import replace_slashes_with_arrows
from ext.feishu import FeishuClient
from ext.dingtalk import DingTalkClient

import httpx
from loguru import logger
from urllib.parse import quote


class Notifier:
    def __init__(self):
        pipes = settings.notify.pipes
        self.notifiers = []
        if pipes:  # 如果 pipes 是真值 (即已提供且不为空)
            self.pipes = pipes
        else:  # 如果 pipes 是 None 或其他假值
            logger.warning("警告！错误提醒通道未配置，将使用默认配置！")
            # 假设 settings.notify.method 存在且不为空
        self.pipes = list(map(int, settings.notify.pipes.split(','))) if settings.notify.pipes else [-1]
        for pipe in self.pipes:
            if pipe == -1:
                self.notifiers = []
            elif pipe == 0:
                self.notifiers.append(FeishuNotifier())
            elif pipe == 1:
                self.notifiers.append(EmailNotifier())
            elif pipe == 2:
                self.notifiers.append(BarkNotifier())
            elif pipe == 3:
                self.notifiers.append(DingTalkNotifier())
            else:
                raise ValueError("pipe must be -1, 0, 1, 2, or 3")

    async def send(self, title: str, content: str):
        # 用 asyncio.gather 并发发送所有通知
        if not self.notifiers:
            return False
        tasks = [
            self._safe_send(notifier, title, content)
            for notifier in self.notifiers
        ]
        results = await asyncio.gather(*tasks)
        return all(results)

    async def _safe_send(self, notifier, title, content):
        try:
            return await notifier.send(replace_slashes_with_arrows(title),
                                       replace_slashes_with_arrows(content))
        except Exception as e:
            logger.error(f"[ERROR] {notifier.__class__.__name__} failed: {e}")
            return False


class FeishuNotifier:
    def __init__(self):
        self.webhook = settings.notify.feishu_webhook
        self.token = settings.notify.feishu_token
        self.platform_url = settings.env.host

    async def send(self, title: str, content: str) -> bool:
        feishu = FeishuClient(self.webhook, self.token)
        asyncio.create_task(feishu.send_card_msg(title, content, self.platform_url))
        # feishu.send_card_msg(title, content, self.platform_url)
        return True


class EmailNotifier:
    def __init__(self):
        self.email = settings.notify.email_host

    async def send(self, title: str, content: str):
        print(f"Email: {self.email}, title: {title}, content: {content}")
        return True


class BarkNotifier:
    def __init__(self):
        self.token = settings.notify.bark_token
        self.host = settings.notify.bark_host

    async def send(self, title: str, content: str):
        url = f"{self.host}/{self.token}/{title}/{quote(content)}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            result = resp.json()
            return result.get("code") == 200


class DingTalkNotifier:
    def __init__(self):
        self.webhook = settings.notify.dingtalk_webhook
        self.token = settings.notify.dingtalk_secret

    async def send(self, title: str, content: str):
        dingding = DingTalkClient(self.webhook, self.token)
        return await dingding.send_markdown_msg(title, content)
