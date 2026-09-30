import asyncio
import sys

sys.path.insert(0, '/ManualAI/OmniKnow/omniknow2/server')

from storage.factory import build_storage_service

# 历史 kb 封面对象：space uuid 作 bucket，images/... 为 key（与上传 URL path 一致）
KEY = '1fc66f3c-31bd-4056-853d-0caadfb32369/images/2026/09/03/b361de030c714886.jpg'


async def main():
    svc = build_storage_service()
    # 与生产同一 presign_backend（endpoint = OSS_WAN http://113.44.11.210:8378）
    url = await svc.presign_backend.presign(KEY, 604800)
    print(url)
    return url


if __name__ == '__main__':
    asyncio.run(main())
