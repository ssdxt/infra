#!/bin/bash
set -e
OUT=/tmp/backup210-20260903.tgz
EXCL=""
for p in '.venv' '__pycache__' 'site-packages' 'node_modules' 'CosyVoice-ttsfrd' 'logs' 'app_logs'; do EXCL="$EXCL --exclude=*/$p --exclude=*/$p/*"; done
EXCL="$EXCL --exclude=*.pyc --exclude=*/tmp/* --exclude=*/nginx/logs/* --exclude=*/nginx/html/*.pdf --exclude=*/output/*"
EXCL="$EXCL --exclude=*/omniknow2.tar.gz --exclude=*/ai-server_*.tar --exclude=*/mysql/data/* --exclude=*/tesla/*"

rm -f "$OUT"
tar czf "$OUT" -C / $EXCL \
  etc/docker/daemon.json \
  etc/cdi/nvidia.yaml \
  etc/udev/rules.d/60-nvidia.rules \
  etc/modules-load.d/nvidia-uvm.conf \
  etc/rc.local \
  root/.config/ngrok \
  ManualAI/docker-compose.yml \
  ManualAI/OmniKnow/docker-omniknow-fixed.yml \
  ManualAI/OmniKnow/docker-omniknow-fixed.yml.bak.20260902 \
  ManualAI/OmniKnow/docker-compose.yml \
  ManualAI/OmniKnow/bash \
  ManualAI/OmniKnow/omniknow2 \
  ManualAI/OmniKnow/data/nginx \
  ManualAI/OmniKnow/data/mineru 2>/dev/null
ls -lh "$OUT"
echo "文件数: $(tar tzf $OUT | wc -l)"
