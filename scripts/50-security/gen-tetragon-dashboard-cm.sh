#!/bin/bash
# 生成 tetragon-dashboard-cm.yaml（从 grafana.com 25789 看板 JSON）
# 在 control-01 执行；也可在 WSL 生成后 scp 过来
set -euo pipefail
DASH_JSON=${1:-tetragon.json}
OUT=${2:-tetragon-dashboard-cm.yaml}
python3 - "$DASH_JSON" "$OUT" <<'EOF'
import json, sys, yaml
dash = json.load(open(sys.argv[1]))
dash.pop('id', None)
cm = {
  'apiVersion': 'v1',
  'kind': 'ConfigMap',
  'metadata': {
    'name': 'tetragon-dashboard',
    'namespace': 'tetragon',
    'labels': {'grafana_dashboard': '1'},
  },
  'data': {'tetragon.json': json.dumps(dash)},
}
yaml.safe_dump(cm, open(sys.argv[2], 'w'), allow_unicode=True, sort_keys=False)
EOF
echo "written $OUT"
