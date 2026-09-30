#!/bin/bash
VLLM=/deploy/models/docker_run/vllm
C=glm-4-9b-chat
LOG=/deploy/logs/mindie/glm-4.log

cd $VLLM || exit 1
sudo docker-compose -f docker-compose.fixed.yml up -d --force-recreate --remove-orphans 2>&1 | grep -v obsolete | tail -4

START=$(date +%s)
for i in $(seq 1 30); do
  sleep 15
  NOW=$(date +%s)
  EL=$((NOW-START))
  ST=$(sudo docker ps -a --filter "name=^${C}$" --format '{{.Status}}' | tr '\n' '|')
  LISTEN=$(ss -tln 2>/dev/null | grep -c ':10006')
  SIZE=$(sudo stat -c %s $LOG 2>/dev/null || echo 0)
  echo "[t=${EL}s] status='$ST' log=$SIZE listen=$LISTEN  last: $(sudo tail -1 $LOG 2>/dev/null | cut -c1-110)"
  if [ "$LISTEN" -gt 0 ]; then echo "*** PORT 10006 LISTENING at t=${EL}s ***"; break; fi
  if echo "$ST" | grep -qi "Restarting\|Exited"; then
     if [ "$EL" -gt 60 ]; then echo "*** CRASH LOOP DETECTED ***"; break; fi
  fi
done

echo
echo "===== final ====="
sudo docker ps -a --filter "name=^${C}$" --format 'table {{.Names}}\t{{.Status}}'
echo "--- log tail 12 ---"
sudo tail -12 $LOG
echo "--- curl ---"
curl -s -m 8 http://127.0.0.1:10006/v1/models | head -c 400
echo
