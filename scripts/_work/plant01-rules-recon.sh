#!/bin/bash
echo "===== plant01 的 python/yaml 能力 ====="
python3 -V
python3 -c 'import yaml; print("pyyaml", yaml.__version__)' 2>&1 | head -2
echo
echo "===== plant01 现有 recording 规则名(用于冲突检查) ====="
python3 - <<'PY'
import json,urllib.request
d=json.load(urllib.request.urlopen('http://localhost:9091/api/v1/rules?type=record',timeout=10))['data']['groups']
names=set()
for g in d:
    for r in g['rules']:
        names.add((r['name'], g['name'], g.get('file','?')))
print('  现有 recording 规则 %d 条:' % len(names))
for n,gn,f in sorted(names):
    print('    %-58s group=%-22s file=%s' % (n,gn,f))
PY
echo
echo "===== plant01 rule_files 实际加载的文件列表 ====="
curl -s 'http://10.100.10.29:9091/api/v1/rules' | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
fs=sorted({g.get('file','?') for g in d})
print('  已加载规则文件:')
for f in fs: print('    ',f)
"
echo
echo "===== promtool 可用性(用于部署前校验) ====="
docker exec wxq-prometheus promtool --version 2>&1 | head -2
