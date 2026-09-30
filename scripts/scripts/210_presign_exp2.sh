#!/bin/bash
cat > /ManualAI/OmniKnow/bash/tmp_presign.py <<'PYEOF'
import asyncio
from aiobotocore.session import AioSession

KEY = 'images/2026/09/03/adb5fc9c83f04f8e.png'
BUCKET = '9f7cf8c6-f866-4c58-9cb0-1ecd091c705c'
AK = 'minioadmin'; SK = 'EVXLpUtzthgyHpI1*ex'

async def main():
    s = AioSession()
    async with s.create_client('s3', endpoint_url='http://minio:9000', aws_access_key_id=AK, aws_secret_access_key=SK, region_name='us-east-1') as c:
        try:
            r = await c.head_object(Bucket=BUCKET, Key=KEY)
            print('HEAD_OK', r['ContentLength'])
        except Exception as e:
            print('HEAD_FAIL', str(e)[:150])
        u1 = await c.generate_presigned_url('get_object', Params={'Bucket': BUCKET, 'Key': KEY}, ExpiresIn=600)
        print('URL1 ' + u1)
    async with s.create_client('s3', endpoint_url='https://snowsuit-swirl-sporty.ngrok-free.dev:443', aws_access_key_id=AK, aws_secret_access_key=SK, region_name='eu-central-1') as c:
        u2 = await c.generate_presigned_url('get_object', Params={'Bucket': BUCKET, 'Key': KEY}, ExpiresIn=600)
        print('URL2 ' + u2)

asyncio.run(main())
PYEOF
echo '== 运行实验 =='
OUT=$(docker exec ai_server /root/anaconda3/envs/aiserver/bin/python /ManualAI/OmniKnow/bash/tmp_presign.py 2>&1)
echo "$OUT" | head -6
rm -f /ManualAI/OmniKnow/bash/tmp_presign.py
U1=$(echo "$OUT" | grep '^URL1 ' | cut -d' ' -f2- | sed 's|http://minio:9000|http://localhost:9000|')
U2=$(echo "$OUT" | grep '^URL2 ' | cut -d' ' -f2-)
echo '== 内网预签名下载 =='
curl -s -o /tmp/a.png -w 'HTTP %{http_code} size %{size_download}\n' "$U1"
echo '== 公网预签名下载 =='
curl -sk -o /tmp/b.png -w 'HTTP %{http_code} size %{size_download}\n' "$U2"
