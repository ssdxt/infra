#!/bin/bash
echo '== restart =='
docker restart ai_server parser ai_server_celery_worker ai_server_celery_beat 2>&1
sleep 18
echo '== status =='
docker ps --format '{{.Names}} | {{.Status}}' | grep -E 'ai_server|parser'
echo '== parser -> mineru connectivity =='
docker exec parser curl -s -o /dev/null -w 'mineru /docs => %{http_code}\n' --max-time 12 http://mineru-api:8000/docs 2>&1 | tail -1
echo '== mineru log tail =='
docker logs mineru-api --tail 6 2>&1 | tail -6
