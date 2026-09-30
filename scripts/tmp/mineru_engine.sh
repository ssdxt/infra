#!/bin/bash
echo "== vlm engine selection =="
docker exec mineru-api grep -rn "Using transformers as the inference engine\|get_vlm_engine\|import vllm\|transformers as the" /opt/venv/lib/python3.12/site-packages/mineru/ --include="*.py" 2>/dev/null | head -10
echo "== env switches around vllm/engine =="
docker exec mineru-api grep -rn "getenv\|environ" /opt/venv/lib/python3.12/site-packages/mineru/backend/vlm/*.py 2>/dev/null | head -15
echo "== files in backend/vlm =="
docker exec mineru-api ls /opt/venv/lib/python3.12/site-packages/mineru/backend/vlm/ 2>/dev/null
