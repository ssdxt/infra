import aioboto3
from dotenv import load_dotenv
import os
load_dotenv()

OSS_HOST = os.getenv("OSS_HOST")
OSS_PORT = int(os.getenv("OSS_PORT"))
OSS_ACCESS_KEY = os.getenv("OSS_ACCESS_KEY")
OSS_ACCESS_SECRET= os.getenv("OSS_ACCESS_SECRET")




class RustFSClient:
    def __init__(self):
        ssl = 0
        protocol = 'https' if ssl else 'http'

        self.session = aioboto3.Session()
        self.client_kwargs = {
            "service_name": "s3",
            "endpoint_url": f"{protocol}://{OSS_HOST}:{OSS_PORT}",
            "aws_access_key_id": OSS_ACCESS_KEY,
            "aws_secret_access_key": OSS_ACCESS_SECRET,
            "region_name": "eu-central-1",
        }

    def _get_client(self):
        return self.session.client(**self.client_kwargs)

    async def check_oss_connection(self):
        async with self._get_client() as s3:
            response = await s3.list_buckets()
        return len(response['Buckets'])

    async def list_buckets(self):
        async with self._get_client() as s3:
            response = await s3.list_buckets()
        return response['Buckets']

    async def create_bucket(self, bucket_name: str):
        async with self._get_client() as s3:
            await s3.create_bucket(Bucket=bucket_name)
        return True

    async def create_folder(self, bucket_name: str, folder_name: str):
        """在指定存储桶中创建文件夹（通过创建一个以斜杠结尾的空对象实现）"""
        if not folder_name.endswith('/'):
            folder_name += '/'
        async with self._get_client() as s3:
            await s3.put_object(Bucket=bucket_name, Key=folder_name)
        return True

    async def init_kbase_bucket(self, bucket_name: str, kbase_name: str):
        """初始化空间存储桶，创建默认文件夹"""
        # 创建默认文件夹
        await self.create_folder(bucket_name, kbase_name)
        await self.create_folder(bucket_name, f'{kbase_name}/images')
        await self.create_folder(bucket_name, f'{kbase_name}/documents/source')
        await self.create_folder(bucket_name, f'{kbase_name}/documents/processed/images')
        return True

    async def upload_file(self, bucket_name: str, object_name: str, file_data: bytes):
        """上传文件到指定存储桶"""
        async with self._get_client() as s3:
            await s3.put_object(Bucket=bucket_name, Key=object_name, Body=file_data)
        return True

    async def get_file_url(self, bucket_name: str, object_name: str, expires_in: int = 3600):
        """获取文件的预签名URL"""
        async with self._get_client() as s3:
            url = await s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_name},
                ExpiresIn=expires_in
            )
        return url
    
    
    
rust = RustFSClient()
