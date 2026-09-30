#!/bin/bash
echo "===== /deploy/code ====="
ls -la /deploy/code/
echo "--- find app configs ---"
sudo find /deploy/code -maxdepth 4 -name "model_config.py" 2>/dev/null
sudo find /deploy/code -maxdepth 3 -name "kb_config.py" 2>/dev/null

echo
echo "===== model endpoints in code ====="
for f in $(sudo find /deploy/code -maxdepth 4 -name "model_config.py" 2>/dev/null | head -2); do
  echo "--- $f ---"
  sudo grep -nE "http://|:[0-9]{4}|model_name|MODEL_NAME|glm|bge" "$f" | head -30
done

echo
echo "===== current user compose file (may have changed again) ====="
sudo ls -la /deploy/models/docker_run/vllm/
sudo md5sum /deploy/models/docker_run/vllm/docker-compose.yml
