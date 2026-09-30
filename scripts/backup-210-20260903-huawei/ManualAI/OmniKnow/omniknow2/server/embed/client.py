from openai import AsyncOpenAI
from openai import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    APIConnectionError,
    APITimeoutError
)

from core.config import settings
from utils.log import logger


class EmbedClient:
    """
    文档解析服务客户端。
    负责将解析任务发送到解析 API 服务器。
    """

    def __init__(self):
        self.api_url = settings.embed.api_url
        self.embed_model = settings.embed.model_name
        self.api_key = settings.embed.api_key
        self.dimension = settings.embed.dimension

    async def embed_data(self, embed_string: str) -> list[float]:
        """
        将解析任务发送到解析 API 服务器。
        task_data 应包含所有必要的任务上下文和解析配置。
        """
        client = AsyncOpenAI(
            base_url=self.api_url,
            api_key=self.api_key
        )
        try:
            responses = await client.embeddings.create(
                input=embed_string,
                model=self.embed_model,
                dimensions=self.dimension
            )
            return responses.data[0].embedding
        except AuthenticationError:
            logger.error("Embedding模型 认证失败，请检查 API Key 配置")
            raise
        except BadRequestError as e:
            logger.error(f"Embedding模型 请求错误: {e}")
            raise
        except RateLimitError:
            logger.error("Embedding模型 请求过于频繁，已被限流")
            raise
        except APIConnectionError:
            logger.error("Embedding模型 无法连接到 API 服务器")
            raise
        except Exception as e:
            logger.error(f"Embedding模型 发生未知错误: {e}")
            raise