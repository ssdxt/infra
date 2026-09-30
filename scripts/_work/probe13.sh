#!/bin/bash
echo "########## pythonlog 目录 ##########"
sudo ls -la /tmp/mllm/pythonlog.log/
echo
for f in /tmp/mllm/pythonlog.log/*; do
  echo "########## $f ##########"
  sudo tail -70 "$f"
  echo
done
echo "########## mindie_audit.log ##########"
sudo cat /tmp/mlogs2/mindie_audit.log
