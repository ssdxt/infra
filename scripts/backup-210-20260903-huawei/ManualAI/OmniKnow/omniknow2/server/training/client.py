import re

import httpx

from core.config import settings
from utils.log import logger


class TrainingClient:
    """封装培训模块的外部 AI 服务调用（考题生成 & 简答题评分 & 考试评价）"""

    def __init__(self):
        self.base_url = settings.training.base_url.rstrip("/")
        self.timeout = settings.training.timeout

    async def generate_questions(self, collection_name: str, file_ids: list[str]) -> dict:
        """
        调用外部 AI 服务生成考题（4 道选择题 + 1 道简答题）。

        POST /api/quest/generate

        :param collection_name: 知识库集合名称
        :param file_ids: 文件 ID 列表
        :return: 包含 collection_name, file_id, title, content[] 的字典
                 content 中每项含 question_type("选择"/"问答"), question_name,
                 options[], chunk_ids[], answer
        :raises httpx.TimeoutException: 请求超时
        :raises httpx.HTTPStatusError: HTTP 非 2xx 响应
        """
        url = f"{self.base_url}/api/quest/generate"
        payload = {
            "collection_name": collection_name,
            "file_ids": file_ids,
        }

        logger.info(f"[TrainingClient] 请求考题生成: collection={collection_name}, files={file_ids}")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            logger.info(f"[TrainingClient] 考题生成完成: title={data.get('title')}, "
                         f"题目数量={len(data.get('content', []))}")
            return data
        except httpx.HTTPStatusError as e:
            logger.error(f"[TrainingClient] 考题生成失败: {e.response.status_code} {e.response.text}")
            raise
        except httpx.TimeoutException:
            logger.error(f"[TrainingClient] 考题生成超时 after {self.timeout} seconds")
            raise
        except Exception as e:
            logger.error(f"[TrainingClient] 考题生成异常: {str(e)}")
            raise

    async def score_short_answer(self, exam_answer: str, standard_answer: str) -> dict:
        """
        调用外部 AI 服务对简答题评分。

        POST /api/quest/score

        :param exam_answer: 学生作答内容
        :param standard_answer: 标准答案
        :return: {"score": int, "reason": str}
        :raises httpx.TimeoutException: 请求超时
        :raises httpx.HTTPStatusError: HTTP 非 2xx 响应
        """
        url = f"{self.base_url}/api/quest/score"
        payload = {
            "exam_answer": exam_answer,
            "standard_answer": standard_answer,
        }

        logger.info(f"[TrainingClient] 请求简答题评分")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        logger.info(f"[TrainingClient] 评分完成: score={data.get('score')}, reason={data.get('reason')}")
        return data

    async def evaluate_exam(self, exam_records: list) -> str:
        """
        调用外部 AI 服务对用户考试记录进行综合评价，返回 Markdown 格式的评价内容。

        POST /api/quest/evaluate

        :param exam_records: 考试记录列表，每项包含 collection_name, file_id, file_name,
                             content[]（含 title, question_type, question_name, options,
                             chunk_ids, answer, score, reason 等字段）
        :return: Markdown 格式的评价文本（已去除 ``` 包裹）
        :raises httpx.TimeoutException: 请求超时
        :raises httpx.HTTPStatusError: HTTP 非 2xx 响应
        """
        url = f"{self.base_url}/api/quest/evaluate"

        logger.info(f"[TrainingClient] 请求考试评价: 共 {len(exam_records)} 份记录")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=exam_records)
                resp.raise_for_status()
                raw_text = resp.text

            # 去除 ```markdown ... ``` 或 ``` ... ``` 包裹
            markdown = re.sub(r"^```(?:markdown)?\s*\n?", "", raw_text.strip())
            markdown = re.sub(r"\n?```\s*$", "", markdown)

            logger.info(f"[TrainingClient] 考试评价完成: 内容长度 {len(markdown)} 字符")
            return markdown
        except httpx.HTTPStatusError as e:
            logger.error(f"[TrainingClient] 考试评价请求失败: {e.response.status_code} {e.response.text}")
            raise
        except httpx.TimeoutException:
            logger.error(f"[TrainingClient] 考试评价请求超时 after {self.timeout} seconds")
            raise
        except Exception as e:
            logger.error(f"[TrainingClient] 考试评价请求异常: {str(e)}")
            raise
