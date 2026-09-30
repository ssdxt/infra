#!/bin/bash
set -e
TS=$(date +%H%M%S)

echo '===== 1. 备份 ====='
cp /ManualAI/OmniKnow/omniknow2/server/storage/service.py /ManualAI/OmniKnow/omniknow2/server/storage/service.py.bak.$TS
cp /ManualAI/OmniKnow/omniknow2/parser/rag/.env /ManualAI/OmniKnow/omniknow2/parser/rag/.env.bak.$TS
cp /ManualAI/OmniKnow/data/mineru/docker-compose.yml /ManualAI/OmniKnow/data/mineru/docker-compose.yml.bak.$TS
echo 'backed up'

echo '===== 2. 补丁: save_space_image/logo 前 ensure 桶 ====='
python2 - <<'PYEOF'
p = '/ManualAI/OmniKnow/omniknow2/server/storage/service.py'
s = open(p, 'rb').read().decode('utf-8')
for anchor_fn, key_fn in [('space_image_key', 'space_image_key'), ('space_logo_key', 'space_logo_key')]:
    a = '        body, content_type = await self._read_upload(file)\n        key = paths.%s(space_id, ' % key_fn
    b = '        await self.ensure_space_bucket(space_id)\n        body, content_type = await self._read_upload(file)\n        key = paths.%s(space_id, ' % key_fn
    assert s.count(a) == 1, (key_fn, s.count(a))
    s = s.replace(a, b)
open(p, 'wb').write(s.encode('utf-8'))
print('patched')
PYEOF
grep -n 'ensure_space_bucket(space_id)' /ManualAI/OmniKnow/omniknow2/server/storage/service.py | head -5

echo '===== 3. 修 rag/.env 的 mineru 与 callback ====='
sed -i 's|MINERU_API=http://192.168.0.23:8000|MINERU_API=http://mineru-api:8000|' /ManualAI/OmniKnow/omniknow2/parser/rag/.env
sed -i 's|CALLBACK_HOST=http://localhost:8375/api/v1|CALLBACK_HOST=http://ai_server:8375/api/v1|' /ManualAI/OmniKnow/omniknow2/parser/rag/.env
grep -nE 'MINERU_API|CALLBACK_HOST' /ManualAI/OmniKnow/omniknow2/parser/rag/.env

echo '===== 4. 重写 mineru compose（清 command、进 cc-net、GPU1 util0.4） ====='
cat > /ManualAI/OmniKnow/data/mineru/docker-compose.yml <<'EOF'
services:
  mineru-api:
    image: mineru:2.6.7
    container_name: mineru-api
    restart: always
    ports:
      - "8000:8000"
    environment:
      MINERU_MODEL_SOURCE: local
    entrypoint: mineru-api
    command:
      - --host
      - 0.0.0.0
      - --port
      - "8000"
      - --gpu-memory-utilization
      - "0.4"
    ulimits:
      memlock: -1
      stack: 67108864
    ipc: host
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/docs || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["1"]
              capabilities: [gpu]
    networks:
      - cc-net

networks:
  cc-net:
    external: true
EOF
echo 'compose rewritten:'
grep -nE 'device_ids|cc-net|command|- --|utilization|0.4' /ManualAI/OmniKnow/data/mineru/docker-compose.yml | head -12

echo '===== 5. 启动 mineru-api ====='
cd /ManualAI/OmniKnow/data/mineru && docker-compose up -d 2>&1 | tail -4
