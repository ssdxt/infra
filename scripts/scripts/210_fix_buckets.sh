#!/bin/bash
echo '===== 日志里 NoSuchBucket 的上下文（找 space） ====='
grep -B10 'NoSuchBucket' /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | grep -E 'save_space|space_image_key|PUT|key|images/' | tail -6
echo
echo '===== DB 里的 spaces 表 ====='
docker exec cc-mysql mysql -uroot -p'Chicheng!234' omniknow -e 'SHOW TABLES LIKE "%space%";' 2>/dev/null | head -10
echo '--- space 列表 ---'
for t in spaces space; do
  docker exec cc-mysql mysql -uroot -p'Chicheng!234' omniknow -e "SELECT id FROM $t LIMIT 20;" 2>/dev/null && break
done
echo
echo '===== 补建缺失 bucket（public + 所有 DB space + 已有对照） ====='
docker exec ai_server python -c "
import asyncio
from aiobotocore.session import AioSession
async def main():
    s = AioSession()
    async with s.create_client('s3', endpoint_url='http://minio:9000', aws_access_key_id='minioadmin', aws_secret_access_key='EVXLpUtzthgyHpI1*ex', region_name='us-east-1') as c:
        r = await c.list_buckets()
        have = {b['Name'] for b in r['Buckets']}
        want = ['public','9f7cf8c6-f866-4c58-9cb0-1ecd091c705c','bd6a6c1c-19ac-47f4-a66b-8c624c2f2470']
        for b in want:
            if b not in have:
                try:
                    await c.create_bucket(Bucket=b)
                    print('created:', b)
                except Exception as e:
                    print('skip', b, str(e)[:80])
            else:
                print('exists:', b)
asyncio.run(main())
" 2>&1 | tail -8
