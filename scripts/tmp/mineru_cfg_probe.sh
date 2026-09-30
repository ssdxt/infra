#!/bin/bash
echo "== models_download_utils =="
docker exec mineru-api sed -n '1,60p' /opt/venv/lib/python3.12/site-packages/mineru/utils/models_download_utils.py 2>/dev/null
echo "== who loads local config =="
docker exec mineru-api grep -rn "local_models_config\|models-dir\|models_dir" /opt/venv/lib/python3.12/site-packages/mineru/ --include="*.py" 2>/dev/null | head -15
