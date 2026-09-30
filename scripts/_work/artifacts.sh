#!/bin/bash
echo "===== 备份目录 (plant01) ====="
ls -la /data1/apps/wxq-plant01-monitor/BACKUP-20260929-141202/
echo
echo "--- inspect 文件 ---"
ls -la /data1/apps/wxq-plant01-monitor/BACKUP-20260929-141202/inspect/
echo
echo "===== 本次改动涉及的文件 ====="
for f in \
  /data1/apps/wxq-plant01-monitor/prometheus/prometheus.yml \
  /data1/apps/wxq-plant01-monitor/prometheus/rules/cluster-wxq-rules.yaml ; do
  printf '  %-72s %s  %s\n' "$f" "$(stat -c '%s bytes' "$f")" "$(md5sum "$f" | cut -c1-12)"
done
echo
echo "===== prometheus.yml 的 rule_files ====="
grep -n 'rule_files' -A2 /data1/apps/wxq-plant01-monitor/prometheus/prometheus.yml | sed 's/^/  /'
echo
echo "===== Rules 文件统计 ====="
python3 - <<'PY'
import yaml
p='/data1/apps/wxq-plant01-monitor/prometheus/rules/cluster-wxq-rules.yaml'
d=yaml.safe_load(open(p))
gs=d['groups']
a=sum(1 for g in gs for r in g['rules'] if 'alert' in r)
r_=sum(1 for g in gs for r in g['rules'] if 'record' in r)
print('  groups = %d  alerting = %d  recording = %d  合计 = %d' % (len(gs),a,r_,a+r_))
PY
