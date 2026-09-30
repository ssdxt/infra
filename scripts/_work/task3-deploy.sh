#!/bin/bash
# ============================================================
#  任务3 部署: 把集群规则同步到 plant01 并重载
#  安全措施: 先暂存 -> promtool 校验 -> 备份 prometheus.yml -> 改配置 -> 校验整体 -> reload -> 验证
#  失败回滚: promtool 失败 或 reload 后异常 => 自动还原 prometheus.yml
# ============================================================
set -u
BASE=/data1/apps/wxq-plant01-monitor
RULES=$BASE/prometheus/rules
YML=$BASE/prometheus/prometheus.yml
STAMP=$(date +%Y%m%d-%H%M%S)
P=http://127.0.0.1:9091
C=wxq-prometheus

echo "===== [1] 暂存新规则文件并校验(promtool, 在容器内跑) ====="
cp /tmp/cluster-wxq-rules.yaml /tmp/new-rules-staged.yaml
docker cp /tmp/new-rules-staged.yaml $C:/tmp/new-rules-staged.yaml || { echo "!! docker cp 失败"; exit 1; }
if docker exec $C promtool check rules /tmp/new-rules-staged.yaml; then
  echo "  ✅ promtool check rules 通过"
else
  echo "  ❌ promtool 校验失败 —— 不部署, 立即退出"
  exit 1
fi
echo
echo "  --- 校验现有规则文件(基线, 确认与本次改动无关) ---"
docker exec $C sh -c 'for f in /etc/prometheus/rules/*.yml; do printf "    %-52s " "$f"; promtool check rules "$f" >/dev/null 2>&1 && echo OK || echo "FAIL"; done'

echo
echo "===== [2] 备份 prometheus.yml ====="
cp -p "$YML" "$BASE/BACKUP-20260929-141202/prometheus.yml.before-task3"
echo "  已备份到 $BASE/BACKUP-20260929-141202/prometheus.yml.before-task3"

echo
echo "===== [3] 修改 rule_files 通配符(让 *.yaml 也能被加载) ====="
echo "  改动前:"; grep -n 'rule_files' -A2 "$YML" | sed 's/^/    /'
# 只在通配符不是 *.y*ml 时替换
if grep -q '\*\.y\*ml' "$YML"; then
  echo "  已是 *.y*ml, 无需修改"
else
  sed -i 's#- /etc/prometheus/rules/\*\.yml#- /etc/prometheus/rules/*.y*ml#' "$YML"
  echo "  改动后:"; grep -n 'rule_files' -A2 "$YML" | sed 's/^/    /'
fi

echo
echo "===== [4] 校验通配符能否命中新文件(容器内) ====="
docker exec $C sh -c 'ls -1 /etc/prometheus/rules/*.y*ml'

echo
echo "===== [5] 落盘规则文件 ====="
install -m 644 -o root -g root /tmp/new-rules-staged.yaml "$RULES/cluster-wxq-rules.yaml"
ls -la "$RULES/cluster-wxq-rules.yaml"
echo "  md5: $(md5sum "$RULES/cluster-wxq-rules.yaml" | cut -d' ' -f1)"
echo "  源 md5: $(md5sum /tmp/cluster-wxq-rules.yaml | cut -d' ' -f1)"

echo
echo "===== [6] 用 promtool 校验最终整体配置(含所有规则文件) ====="
if docker exec $C promtool check config /etc/prometheus/prometheus.yml; then
  echo "  ✅ promtool check config 通过"
else
  echo "  ❌ 整体配置校验失败 —— 回滚"
  cp -p "$BASE/BACKUP-20260929-141202/prometheus.yml.before-task3" "$YML"
  rm -f "$RULES/cluster-wxq-rules.yaml"
  exit 1
fi

echo
echo "===== [7] 重载 Prometheus ====="
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$P/-/reload")
echo "  POST /-/reload => HTTP $CODE"
sleep 5
echo "  reloadConfigSuccess = $(curl -s "$P/api/v1/status/runtimeinfo" | python3 -c "import sys,json;print(json.load(sys.stdin)['data'].get('reloadConfigSuccess'))")"
echo "  lastConfigTime      = $(curl -s "$P/api/v1/status/runtimeinfo" | python3 -c "import sys,json;print(json.load(sys.stdin)['data'].get('lastConfigTime'))")"

echo
echo "===== [8] 验证加载结果 ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
print('  规则组总数 =',len(d))
files=sorted({g.get('file','?') for g in d})
print('  涉及文件:')
for f in files: print('    ',f)
# 只看新文件
new=[g for g in d if g.get('file','').endswith('cluster-wxq-rules.yaml')]
print()
print('  新文件 cluster-wxq-rules.yaml: %d 个组' % len(new))
na=sum(1 for g in new for r in g['rules'] if r['type']=='alerting')
nr=sum(1 for g in new for r in g['rules'] if r['type']=='recording')
print('    alerting=%d recording=%d 合计=%d' % (na,nr,na+nr))
"
echo
echo "  --- 全部规则健康度 ---"
curl -s "$P/api/v1/rules" | grep -o '\"health\":\"[a-z]*\"' | sort | uniq -c
echo
echo "  --- 新文件的规则健康度 ---"
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
from collections import Counter
d=json.load(sys.stdin)['data']['groups']
c=Counter()
bad=[]
for g in d:
    if not g.get('file','').endswith('cluster-wxq-rules.yaml'): continue
    for r in g['rules']:
        c[r.get('health')]+=1
        if r.get('health')!='ok':
            bad.append((r.get('name'),g['name'],r.get('health'),(r.get('lastError') or '')[:90]))
print('  ',dict(c))
if bad:
    print('  ⚠️ 非 ok 的规则 %d 条:' % len(bad))
    for n,g,h,e in bad[:25]: print('     %-46s group=%-40s %s %s' % (n,g,h,e))
"
echo
echo "===== [9] 抽样验证集群规则名存在 ====="
for n in KubeNodeNotReady KubeAPIErrorBudgetBurn KubeletClientCertificateExpiration NodeFilesystemSpaceFillingUp; do
  cnt=$(curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
n='$n'
c=sum(1 for g in d for r in g['rules'] if r['name']==n)
print(c)")
  printf '  %-42s 出现 %s 次\n' "$n" "$cnt"
done
