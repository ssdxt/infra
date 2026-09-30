#!/bin/bash
echo '== OmniKnow top structure =='
docker exec ai_server ls /ManualAI/OmniKnow/ 2>&1 | head -25
echo '== models dir =='
docker exec ai_server ls /ManualAI/OmniKnow/models/ 2>&1 | head -20
echo '== config refs to embedding/8021 =='
docker exec ai_server sh -c "grep -rInE '8021|qwen-embedding|EMBEDDING' /ManualAI/OmniKnow --include='*.env' --include='*.yml' --include='*.yaml' --include='*.json' --include='*.conf' --include='*.ini' 2>/dev/null | head -15"
echo '== ai_server env GPU-related =='
docker inspect ai_server --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep -iE 'embed|cuda|gpu|8021|8022' | head -10
echo '== cuda runfile size (for cleanup) =='
ls -lh /root/cuda_12.8.0_570.86.10_linux.run 2>&1
