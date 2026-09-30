#!/bin/bash
docker logs mineru-api --tail 120 2>&1 | grep -iE 'error|fail|oom|memory|not support|assert|raise|cuda|torch.cuda|OutOfMemory|No available' | head -30
echo "==== last 25 lines ===="
docker logs mineru-api --tail 25 2>&1
