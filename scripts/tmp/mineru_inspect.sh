#!/bin/bash
echo "== Dockerfile =="
cat /ManualAI/llm/mineru/Dockerfile 2>/dev/null | head -40
echo "== mineru pkg/models =="
docker exec mineru-api sh -c 'python3 -c "import mineru,os;print(os.path.dirname(mineru.__file__))"'
docker exec mineru-api sh -c 'find / -maxdepth 5 -iname "*mineru*" -type d 2>/dev/null | grep -viE "proc|sys|dist-packages/mineru$|site-packages/mineru" | head -10'
echo "== look for model dirs =="
docker exec mineru-api sh -c 'find /root /opt /usr/local -maxdepth 5 -type d -iname "*model*" 2>/dev/null | head -10; du -sh /opt/models /root/models 2>/dev/null'
