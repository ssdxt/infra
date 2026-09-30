import aioboto3
from typing import List, Optional
import asyncio
import httpx
import aiofiles
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv
import os
load_dotenv()

class AsyncOSSClient:
    """
    Async OSS client based on aioboto3 (S3 compatible)

    Example:
        oss = AsyncOSSClient(
            endpoint="oss-cn-hangzhou.aliyuncs.com",
            access_key_id="xxx",
            access_key_secret="xxx",
            bucket_name="my-bucket"
        )
        await oss.upload_file("a.txt", "test/a.txt")
    """

    def __init__(
        self,
        bucket_name: str,
    ):
        self.bucket_name = bucket_name

        self.session = aioboto3.Session()
        
        self.client_kwargs = {
            "service_name": "s3",
            "endpoint_url": f"{os.getenv('OSS_PROTOCOL')}://{os.getenv('OSS_HOST')}:{os.getenv('OSS_PORT')}",
            "aws_access_key_id": os.getenv("OSS_ACCESS_KEY"),
            "aws_secret_access_key": os.getenv("OSS_ACCESS_SECRET"),
            "region_name": os.getenv("OSS_REGION_NAME"),
        }


    def _get_client(self):
        return self.session.client(**self.client_kwargs)


    async def list_objects(self, prefix: str = "") -> List[str]:
        """列出 bucket 中的对象"""
        keys = []

        async with self._get_client() as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(
                Bucket=self.bucket_name, Prefix=prefix
            ):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])

        return keys

    async def upload_file(
        self,
        local_path: str,
        object_key: str,
        content_type: Optional[str] = None,
    ):
        """上传本地文件到 OSS"""
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        async with self._get_client() as client:
            await client.upload_file(
                local_path,
                self.bucket_name,
                object_key,
                ExtraArgs=extra_args or None,
            )
        # {bucket_name}/{kb_name}/documents/processed/images

    async def download_file(self, object_key: str, local_path: str):
        """从 OSS 下载文件"""
        async with self._get_client() as client:
            await client.download_file(
                self.bucket_name,
                object_key,
                local_path,
            )

    async def delete_object(self, object_key: str):
        """删除 OSS 文件"""
        async with self._get_client() as client:
            await client.delete_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )

    async def exists(self, object_key: str) -> bool:
        """判断对象是否存在"""
        async with self._get_client() as client:
            try:
                await client.head_object(
                    Bucket=self.bucket_name,
                    Key=object_key,
                )
                return True
            except Exception:
                return False


    async def download_from_oss(self, url: str):
        filename = unquote(urlparse(url).path).split("/")[-1]
        save_path = os.path.abspath(os.path.join("./downloads", filename))
        
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()

                async with aiofiles.open(save_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                        await f.write(chunk)
        
        return save_path
                        
async def main():
    oss = AsyncOSSClient("1d547526-5684-4ffe-b628-26ffedd2c8ff")

    # 上传
    # await oss.upload_file("test.txt", "docs/test.txt")

    # 判断是否存在
    # print(await oss.exists("docs/test.txt"))

    # 列出文件
    # files = await oss.list_objects(prefix="docs/")
    # files = await oss.list_objects()
    # print(files)
    url = "http://localhost:9001/1d547526-5684-4ffe-b628-26ffedd2c8ff/%E6%B5%8B%E8%AF%95%E5%BA%93/documents/source/%E5%9F%BA%E4%BA%8E%E5%A4%A7%E6%A8%A1%E5%9E%8B%E7%9A%84%E6%9F%90%E7%BB%B4%E4%BF%AE%E5%8A%A9%E6%89%8B%E5%8E%9F%E5%9E%8B%E7%B3%BB%E7%BB%9F-%E7%94%A8%E6%88%B7%E7%AB%AF%E4%BD%BF%E7%94%A8%E6%89%8B%E5%86%8C.docx?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=MZ8JLYCK4Q89GSA4D5WA%2F20251223%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20251223T111846Z&X-Amz-Expires=86400&X-Amz-Security-Token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJleHAiOjE3NjY1MTY4NDYsInBhcmVudCI6ImFpX3NlcnZlciJ9.iNYLF2L_LqXHUru04JSbzebtJwRiipNRkhDvCjUqSAQyp8ZflZcDWaw89Y0qQe--0wxYzb4qG9R9z45loLS-gw&X-Amz-Signature=be14e9c6ac503c8d32b608140105334c9d6dc1d7678e43fb648449d2ce26b123&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject"
    
    file_path = await oss.download_from_oss(url)
    print(file_path)
    # 下载
    # await oss.download_file("docs/test.txt", "test_download.txt")

    # # 删除
    # await oss.delete_object("docs/test.txt")


if __name__ == "__main__":
    asyncio.run(main())

    # url = "http://localhost:9001/1d547526-5684-4ffe-b628-26ffedd2c8ff/%E6%B5%8B%E8%AF%95%E5%BA%93/documents/source/%E5%9F%BA%E4%BA%8E%E5%A4%A7%E6%A8%A1%E5%9E%8B%E7%9A%84%E6%9F%90%E7%BB%B4%E4%BF%AE%E5%8A%A9%E6%89%8B%E5%8E%9F%E5%9E%8B%E7%B3%BB%E7%BB%9F-%E7%94%A8%E6%88%B7%E7%AB%AF%E4%BD%BF%E7%94%A8%E6%89%8B%E5%86%8C.docx?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=MZ8JLYCK4Q89GSA4D5WA%2F20251223%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20251223T111846Z&X-Amz-Expires=86400&X-Amz-Security-Token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJleHAiOjE3NjY1MTY4NDYsInBhcmVudCI6ImFpX3NlcnZlciJ9.iNYLF2L_LqXHUru04JSbzebtJwRiipNRkhDvCjUqSAQyp8ZflZcDWaw89Y0qQe--0wxYzb4qG9R9z45loLS-gw&X-Amz-Signature=be14e9c6ac503c8d32b608140105334c9d6dc1d7678e43fb648449d2ce26b123&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject"

    # from urllib.parse import urlparse, unquote
    # filename = unquote(urlparse(url).path).split("/")[-1]
    # filename = os.path.basename(filename)
    # ext = os.path.splitext(filename)[1]
    # print(filename)
    # print(ext)
    