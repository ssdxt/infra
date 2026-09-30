#!/bin/bash
# ============================================================
#  修复 rule_files 通配符 —— 必须"原地写"(不能 sed -i / mv)
#
#  教训: /etc/prometheus/prometheus.yml 是单文件 bind mount。
#        `sed -i` 会新建临时文件再 rename → 宿主机 inode 变了,
#        但容器仍绑在【被 unlink 的旧 inode】上, 看到的还是老内容。
#        必须用 `cat > 文件` 原地覆盖, 保持 inode 不变。
# ============================================================
set -u
BASE=/data1/apps/wxq-plant01-monitor
YML=$BASE/prometheus/prometheus.yml
C=wxq-prometheus
P=http://127.0.0.1:9091

echo "===== [0] 现状(inode 应不一致, 说明之前被 sed -i 打断了挂载) ====="
echo -n "  宿主机 inode : "; stat -c '%i  (%s bytes)  %.19y' "$YML"
echo -n "  容器内 inode : "; docker exec $C stat -c '%i  (%s bytes)  %.19y' /etc/prometheus/prometheus.yml

echo
echo "===== [1] 备份当前宿主机文件 ====="
cp -p "$YML" "$BASE/BACKUP-20260929-141202/prometheus.yml.before-inplace-fix"
echo "  已备份"

echo
echo "===== [2] 原地覆盖(保持 inode): 把 *.yml 改为 *.y*ml ====="
# 记录旧 inode
OLD_INO=$(stat -c '%i' "$YML")
sed 's#/etc/prometheus/rules/\*\.yml#/etc/prometheus/rules/*.y*ml#' "$YML" > /tmp/prom-new.yml
# 原地写入同一 inode
cat /tmp/prom-new.yml > "$YML"
# 清掉可能残留的临时文件(不动挂载中的文件)
rm -f /tmp/prom-new.yml
NEW_INO=$(stat -c '%i' "$YML")
echo "  宿主机 inode: $OLD_INO -> $NEW_INO  $([ "$OLD_INO" = "$NEW_INO" ] && echo '✅ 未变(挂载保持)' || echo '❌ 变了!')"

echo
echo "===== [3] 容器内应立刻看到新内容(验证挂载已通) ====="
docker exec $C sh -c 'grep -n "rule_files" -A2 /etc/prometheus/prometheus.yml' | sed 's/^/  /'
echo -n "  容器内 inode : "; docker exec $C stat -c '%i  (%s bytes)' /etc/prometheus/prometheus.yml
echo -n "  两侧 md5     : 宿主机 $(md5sum "$YML" | cut -c1-32) / 容器 $(docker exec $C md5sum /etc/prometheus/prometheus.yml | cut -c1-32)"

echo
echo "===== [4] promtool 校验整体配置 ====="
docker exec $C promtool check config /etc/prometheus/prometheus.yml 2>&1 | head -6
echo "  --- 是否 9 个规则文件被找到 ---"
docker exec $C promtool check config /etc/prometheus/prometheus.yml 2>&1 | grep -E 'rule files found'

echo
echo "===== [5] 重载 ====="
echo -n "  POST /-/reload => HTTP "; curl -s -o /dev/null -w '%{http_code}\n' -X POST "$P/-/reload"
sleep 8
docker logs $C --since 1m 2>&1 | grep -iE 'rule|error' | tail -8

echo
echo "===== [6] 验证加载结果 ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
from collections import Counter
d=json.load(sys.stdin)['data']['groups']
tot=sum(len(g['rules']) for g in d)
print('  groups = %d   rules = %d' % (len(d),tot))
print()
print('  涉及文件:')
for f in sorted({g.get('file') for g in d}): print('   ',f)
print()
c=Counter()
for g in d:
    for r in g['rules']:
        c[(r['type'],r.get('health'))]+=1
print('  按(类型,健康):')
for k,v in sorted(c.items()): print('    %-24s %s' % (str(k),v))
bad=[(r['name'],g['name'],r.get('health'),(r.get('lastError') or '')[:80]) for g in d for r in g['rules'] if r.get('health')!='ok']
print()
if bad:
    print('  ⚠️ 非 ok 规则 %d 条:' % len(bad))
    for n,g,h,e in bad[:20]: print('     %-46s group=%-40s %s %s' % (n,g,h,e))
else:
    print('  ✅ 全部规则 health=ok')
"
echo
echo "===== [7] 抽样确认集群规则已加载 ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
names={r['name'] for g in d for r in g['rules']}
for n in ['KubeNodeNotReady','KubeAPIErrorBudgetBurn','KubeletClientCertificateExpiration','NodeFilesystemSpaceFillingUp','KubePodCrashLooping','AlertmanagerFailedReload','KubeDeploymentReplicasMismatch','CPUThrottlingHigh']:
    print('    %-44s %s' % (n, '✅' if n in names else '❌'))
"
