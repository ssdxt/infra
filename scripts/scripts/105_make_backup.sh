#!/bin/bash
set -e
OUT=/tmp/backup105-20260903-thor.tgz
EXCL=""
for p in '.venv' '__pycache__' 'site-packages' 'node_modules' 'logs'; do EXCL="$EXCL --exclude=*/$p --exclude=*/$p/*"; done
EXCL="$EXCL --exclude=*.pyc --exclude=*.log --exclude=*/tmp/* --exclude=*/1panel --exclude=*.whl"
rm -f "$OUT"
tar czf "$OUT" -C / $EXCL \
  ManualAI/depends_on/docker-compose.yaml \
  ManualAI/Omniknow \
  ManualAI/MetaManual/docker-compose.yml \
  ManualAI/llm \
  ManualAI/tools \
  ManualAI/system_info \
  usr/local/bin 2>/dev/null || { echo "TAR_FAIL"; exit 1; }
ls -lh "$OUT"
echo "文件数: $(tar tzf $OUT | wc -l)"
echo '== 最大文件 =='
tar tvzf "$OUT" | sort -k3 -n -r | head -6 | awk '{printf "%.1f MB  %s\n", $3/1048576, $6}'
