#!/bin/bash
echo '===== mineru compose 全文 ====='
cat /ManualAI/OmniKnow/data/mineru/docker-compose.yml 2>/dev/null
echo
echo '===== mineru 相关容器/镜像 ====='
docker ps -a --format '{{.Names}} | {{.Image}} | {{.Status}}' 2>/dev/null | grep -i mineru || echo '无 mineru 容器'
docker images | grep -i mineru
echo
echo '===== parser 里 mineru URL 配置 ====='
grep -rniE 'mineru|MINERU' /ManualAI/OmniKnow/omniknow2/parser/rag/.env /ManualAI/OmniKnow/omniknow2/parser/rag/*.py /ManualAI/OmniKnow/omniknow2/parser/rag/**/*.py 2>/dev/null | grep -iE 'url|host|port|api|http|=' | head -12
echo
echo '===== ai_server s3 bucket 相关 ====='
grep -rniE 'bucket|BUCKET' /ManualAI/OmniKnow/omniknow2/server/storage/backends/s3.py 2>/dev/null | head -10
grep -nE 'bucket|BUCKET' /ManualAI/OmniKnow/omniknow2/server/storage/service.py 2>/dev/null | head -15
grep -rniE 'bucket' /ManualAI/OmniKnow/omniknow2/server/.env /ManualAI/OmniKnow/omniknow2/envs/.env-server 2>/dev/null | head
echo
echo '===== minio 现有桶 ====='
docker exec ai_server python -c "
import asyncio, os
from aiobotocore.session import AioSession
async def main():
    s = AioSession()
    async with s.create_client('s3', endpoint_url='http://minio:9000', aws_access_key_id='minioadmin', aws_secret_access_key='EVXLpUtzthgyHpI1*ex', region_name='us-east-1') as c:
        r = await c.list_buckets()
        print('buckets:', [b['Name'] for b in r['Buckets']])
asyncio.run(main())
" 2>&1 | tail -3
