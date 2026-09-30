#!/bin/bash
set -e
echo '== 1. 从备份恢复 =='
cp /ManualAI/OmniKnow/omniknow2/server/storage/factory.py.bak.093914 /ManualAI/OmniKnow/omniknow2/server/storage/factory.py
wc -c /ManualAI/OmniKnow/omniknow2/server/storage/factory.py

echo '== 2. 写 python3 补丁脚本（经 bind 挂载目录进容器执行） =='
cat > /ManualAI/OmniKnow/bash/tmp_patch_factory.py <<'PYEOF'
p = '/ManualAI/OmniKnow/omniknow2/server/storage/factory.py'
s = open(p, encoding='utf-8').read()
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
assert s.count(old) == 1, 'anchor not found'
open(p, 'w', encoding='utf-8').write(s.replace(old, new))
print('patched OK')
PYEOF

echo '== 3. 容器 python3 执行补丁 =='
docker exec assistant /root/anaconda3/bin/python /ManualAI/OmniKnow/bash/tmp_patch_factory.py
rm -f /ManualAI/OmniKnow/bash/tmp_patch_factory.py

echo '== 4. 语法校验 =='
docker exec assistant /root/anaconda3/bin/python - <<'PYEOF'
import ast
ast.parse(open('/ManualAI/OmniKnow/omniknow2/server/storage/factory.py', encoding='utf-8').read())
print('SYNTAX OK')
PYEOF
sed -n '60,80p' /ManualAI/OmniKnow/omniknow2/server/storage/factory.py

echo '== 5. 重建 ai_server =='
cd /ManualAI/OmniKnow
docker-compose -f docker-omniknow-fixed.yml up -d server-api 2>&1 | tail -2
sleep 25
docker ps --format '{{.Names}} | {{.Status}}' | grep ai_server
