#!/bin/bash
docker exec ai_server /root/anaconda3/envs/aiserver/bin/python - <<'PYEOF'
import asyncio
from aiobotocore.session import AioSession

KEY = 'images/2026/09/03/adb5fc9c83f04f8e.png'
BUCKET = '9f7cf8c6-f866-4c58-9cb0-1ecd091c705c'
AK = 'minioadmin'; SK = 'EVXLpUtzthgyHpI1*ex'

async def main():
    s = AioSession()
    # 1. 对象是否存在 + 可读
    async with s.create_client('s3', endpoint_url='http://minio:9000', aws_access_key_id=AK, aws_secret_access_key=SK, region_name='us-east-1') as c:
        try:
            r = await c.head_object(Bucket=BUCKET, Key=KEY)
            print('head_object OK size', r['ContentLength'])
        except Exception as e:
            print('head_object FAIL', str(e)[:120])
        # 2. 内网端点预签名
        u1 = await c.generate_presigned_url('get_object', Params={'Bucket': BUCKET, 'Key': KEY}, ExpiresIn=600)
        print('internal presign:', u1[:120])
        open('/tmp/presign_internal.txt', 'w').write(u1)
        # 3. 公网端点预签名
    async with s.create_client('s3', endpoint_url='https://snowsuit-swirl-sporty.ngrok-free.dev:443', aws_access_key_id=AK, aws_secret_access_key=SK, region_name='eu-central-1') as c:
        u2 = await c.generate_presigned_url('get_object', Params={'Bucket': BUCKET, 'Key': KEY}, ExpiresIn=600)
        print('wan presign:', u2[:120])
        open('/tmp/presign_wan.txt', 'w').write(u2)

asyncio.run(main())
PYEOF
echo '== 内网预签名下载 =='
curl -s -o /tmp/a.png -w 'HTTP %{http_code} size %{size_download}\n' "$(cat /tmp/presign_internal.txt)"
echo '== 公网预签名下载(经 nginx) =='
curl -sk -o /tmp/b.png -w 'HTTP %{http_code} size %{size_download}\n' "$(cat /tmp/presign_wan.txt)"
