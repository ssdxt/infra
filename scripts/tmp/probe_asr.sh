#!/bin/bash
echo "== ports =="
ss -ltn | grep -E ':8023|:8024|:8443' || echo no-listen
echo "== ASR http 8023 =="
curl -s --max-time 8 http://127.0.0.1:8023/health; echo
echo "== ASR https 8443 =="
curl -sk --max-time 8 https://127.0.0.1:8443/health; echo
echo "== TTS log tail =="
docker logs qwen3-tts --tail 6 2>&1 | tail -6
echo "== ASR log tail =="
docker logs qwen3-asr --tail 6 2>&1 | tail -6
