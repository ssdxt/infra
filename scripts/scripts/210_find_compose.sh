#!/bin/bash
echo '== all compose files under /ManualAI =='
find /ManualAI -maxdepth 4 \( -name 'docker-compose*.yml' -o -name 'docker-compose*.yaml' -o -name 'compose*.yml' -o -name 'compose*.yaml' \) 2>/dev/null
echo '== which reference qwen-embedding =='
for f in $(find /ManualAI -maxdepth 4 -name 'docker-compose*.yml' 2>/dev/null); do
  if grep -q 'qwen-embedding' "$f"; then echo "FOUND: $f"; fi
done
echo '== OmniKnow top level =='
ls /ManualAI/OmniKnow/ 2>/dev/null
echo '== qwen-embedding container status now =='
docker ps -a --format '{{.Names}} | {{.Status}}' | grep -E 'qwen'
echo '== any start-stack scripts in /ManualAI =='
ls /ManualAI/*.sh /ManualAI/OmniKnow/*.sh /ManualAI/OmniKnow/bash/*.sh 2>/dev/null | head -20
