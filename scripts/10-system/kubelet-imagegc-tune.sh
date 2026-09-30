#!/bin/bash
# 07-kubelet-imagegc-tune.sh — kubelet 镜像 GC 阈值调优（逐台执行，失败回滚并中止）
# 用法：bash 07-kubelet-imagegc-tune.sh <nodename> <ip>
# 在 control-01 上执行；每台：备份 config → 设 imageGC 70/60 → 重启 kubelet → 验证
set -o pipefail
NODE="$1"; IP="$2"
DATE=$(date +%Y%m%d)
CONF=/var/lib/kubelet/config.yaml
BAK="${CONF}.bak.gc.${DATE}"
# 仅 control 节点有 admin.conf；worker 上 kubectl 检查跳过，由调度侧（control-01）统一验证
if [ -f /etc/kubernetes/admin.conf ]; then export KUBECONFIG=/etc/kubernetes/admin.conf; fi

echo "=== [$NODE $IP] 开始 ==="
echo "--- before: $(df --output=pcent / | tail -1 | tr -d ' ') used, images=$(crictl images -q | wc -l)"

# 1. 备份（幂等：当天已备份则不覆盖）
if [ ! -f "$BAK" ]; then cp -a "$CONF" "$BAK"; fi
echo "backup: $BAK"

# 2. 修改配置（PyYAML 优先，失败则文本插入）
python3 - "$CONF" <<'PYEOF' || { echo "PY_EDIT_FAILED"; exit 2; }
import sys
p = sys.argv[1]
try:
    import yaml
    d = yaml.safe_load(open(p))
    d['imageGCHighThresholdPercent'] = 70
    d['imageGCLowThresholdPercent'] = 60
    open(p, 'w').write(yaml.safe_dump(d, default_flow_style=False, sort_keys=True))
except Exception as e:
    print('PyYAML failed:', e)
    lines = open(p).read().splitlines()
    lines = [l for l in lines if not l.strip().startswith('imageGC')]
    out = []
    for l in lines:
        out.append(l)
        if l.startswith('evictionHard:') or (l.startswith('apiVersion:') and not out[:-1]):
            pass
    # 在文件末尾（子配置均为顶层键）追加两个顶层键
    out.append('imageGCHighThresholdPercent: 70')
    out.append('imageGCLowThresholdPercent: 60')
    open(p, 'w').write('\n'.join(out) + '\n')
print('config updated')
PYEOF
[ $? -ne 0 ] && exit 2

# 校验 yaml 可解析且字段正确，否则回滚退出
python3 - "$CONF" <<'PYEOF' || ROLLBACK=1
import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
assert d.get('imageGCHighThresholdPercent') == 70, d.get('imageGCHighThresholdPercent')
assert d.get('imageGCLowThresholdPercent') == 60, d.get('imageGCLowThresholdPercent')
print('config validated')
PYEOF
if [ "$ROLLBACK" = "1" ]; then
  echo "!!! 校验失败，回滚"
  cp -a "$BAK" "$CONF"; systemctl restart kubelet; exit 2
fi

# 3. 重启 kubelet
systemctl restart kubelet
sleep 10

# 4. 验证
FAIL=0
if [ "$(systemctl is-active kubelet)" != "active" ]; then
  echo "!!! kubelet not active, 回滚"; FAIL=1
else
  if command -v kubectl >/dev/null 2>&1 && [ -n "${KUBECONFIG:-}" ]; then
    READY=""
    for i in $(seq 1 24); do
      READY=$(kubectl get node "$NODE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
      [ "$READY" = "True" ] && break
      sleep 5
    done
    if [ "$READY" != "True" ]; then echo "!!! node not Ready, 回滚"; FAIL=1; fi
  else
    echo "(worker 节点：本机不做 kubectl 检查，由 control-01 侧验证)"
  fi
fi
# 该节点 Pod 异常检查（仅 control 节点本机执行）
BADPODS=""
if command -v kubectl >/dev/null 2>&1 && [ -n "${KUBECONFIG:-}" ]; then
BADPODS=$(kubectl get pods -A --field-selector spec.nodeName="$NODE" \
  -o json | python3 -c '
import json,sys
d=json.load(sys.stdin); bad=[]
for p in d["items"]:
    for s in p.get("status",{}).get("containerStatuses",[]):
        if s.get("restartCount",0)>0 and s.get("state",{}).get("running",{}).get("startedAt","")>"'"$(date -u +%Y-%m-%dT%H)"'":
            bad.append(p["metadata"]["name"]+"/restart")
        if s.get("state",{}).get("waiting",{}).get("reason") in ("CrashLoopBackOff","Error"):
            bad.append(p["metadata"]["name"]+"/"+s["state"]["waiting"]["reason"])
print(",".join(bad))' 2>/dev/null)
fi
if [ -n "$BADPODS" ]; then echo "!!! 异常 Pod: $BADPODS, 回滚"; FAIL=1; fi

if [ "$FAIL" = "1" ]; then
  cp -a "$BAK" "$CONF"; systemctl restart kubelet; sleep 5
  echo "!!! 已回滚（恢复 $BAK 并重启 kubelet）。状态: kubelet=$(systemctl is-active kubelet)"
  exit 2
fi

echo "--- after: $(df --output=pcent / | tail -1 | tr -d ' ') used, images=$(crictl images -q | wc -l)"
echo "=== [$NODE $IP] 完成 OK ==="
