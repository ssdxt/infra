#!/bin/bash
echo '== ai_server 崩溃原因 =='
docker logs ai_server --tail 20 2>&1 | grep -iE 'error|https|ssl|minio|connect|Traceback|raise' | tail -8
echo '== 1. 回退 OSS_SSL=0 =='
sed -i 's|^OSS_SSL=1|OSS_SSL=0|' /ManualAI/OmniKnow/omniknow2/server/.env
grep -nE '^OSS_(SSL|WAN_HOST|WAN_PORT)=' /ManualAI/OmniKnow/omniknow2/server/.env
echo '== 2. 补丁 factory.py：wan 端口 443 时 presign 用 https =='
cp /ManualAI/OmniKnow/omniknow2/server/storage/factory.py /ManualAI/OmniKnow/omniknow2/server/storage/factory.py.bak.$(date +%H%M%S)
python2 - <<'PYEOF'
p = '/ManualAI/OmniKnow/omniknow2/server/storage/factory.py'
s = open(p).read()
old = '''        presign_backend = S3Backend(
            endpoint=_s3_endpoint(oss.wan_host, oss.wan_port, oss.ssl),
            access_key=oss.access_key,
            secret_key=oss.secret_key,
            region=oss.region,
        )
        protocol = "https" if oss.ssl else "http"
        public_url_base = f"{protocol}://{oss.wan_host}:{oss.wan_port}"'''
new = '''        wan_ssl = 1 if (oss.ssl or oss.wan_port == 443) else 0
        presign_backend = S3Backend(
            endpoint=_s3_endpoint(oss.wan_host, oss.wan_port, wan_ssl),
            access_key=oss.access_key,
            secret_key=oss.secret_key,
            region=oss.region,
        )
        protocol = "https" if wan_ssl else "http"
        public_url_base = f"{protocol}://{oss.wan_host}:{oss.wan_port}"'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, 'wb').write(s.encode('utf-8'))
print('factory patched')
PYEOF
echo '== 3. 重建 ai_server =='
cd /ManualAI/OmniKnow
docker-compose -f docker-omniknow-fixed.yml up -d server-api 2>&1 | tail -2
sleep 25
docker ps --format '{{.Names}} | {{.Status}}' | grep ai_server
