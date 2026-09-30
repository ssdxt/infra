#!/bin/bash
# 治理 DNS 噪音（Grafana 上报 + nodelocaldns 外部转发）+ 排查重新出现的燃烧告警
set -u
export KUBECONFIG=/etc/kubernetes/admin.conf
mkdir -p /data1/ssdxt/backup

echo "########## 1. Grafana 关闭使用统计上报（消灭 stats.grafana.org 查询源）##########"
kubectl -n monitoring set env deploy/prometheus-stack-grafana \
  GF_ANALYTICS_REPORTING_ENABLED=false GF_ANALYTICS_CHECK_FOR_UPDATES=false 2>&1 | tail -1
python3 - <<'PY'
try:
    import yaml
    p = "/data1/ssdxt/values/prometheus-stack-values.yaml"
    d = yaml.safe_load(open(p))
    env = d.setdefault("grafana", {}).setdefault("extraEnv", [])
    for it in [{"name": "GF_ANALYTICS_REPORTING_ENABLED", "value": "false"},
               {"name": "GF_ANALYTICS_CHECK_FOR_UPDATES", "value": "false"}]:
        if not any(e.get("name") == it["name"] for e in env):
            env.append(it)
    open(p, "w").write(yaml.safe_dump(d, sort_keys=False, allow_unicode=True))
    print("  ✅ values 已同步 extraEnv（持久化）")
except Exception as e:
    print("  ⚠️ values 未同步:", e)
PY
kubectl -n monitoring rollout status deploy/prometheus-stack-grafana --timeout=180s 2>&1 | tail -1
echo ""

echo "########## 2. nodelocaldns：外部域名快速失败（不再等 5 秒超时）##########"
kubectl -n kube-system get cm nodelocaldns -o yaml > /data1/ssdxt/backup/nodelocaldns-cm-$(date +%m%d-%H%M).yaml
python3 - <<'PY'
import subprocess, json
raw = subprocess.run(["kubectl","-n","kube-system","get","cm","nodelocaldns","-o","json"],
                     capture_output=True, text=True).stdout
d = json.loads(raw)
corefile = d["data"]["Corefile"]
n = corefile.count("forward . /etc/resolv.conf")
if n == 0:
    print("  ⚠️ 未找到 forward . /etc/resolv.conf（可能已改过）")
else:
    corefile = corefile.replace("forward . /etc/resolv.conf", "forward . 127.0.0.1:1")
    d["data"]["Corefile"] = corefile
    open("/tmp/nodelocaldns-new.json","w").write(json.dumps(d))
    subprocess.run(["kubectl","apply","-f","/tmp/nodelocaldns-new.json"], check=True)
    print("  ✅ 已替换 %d 处 forward → 127.0.0.1:1（连接秒拒绝，不再等5秒超时）" % n)
PY
kubectl -n kube-system rollout restart ds/nodelocaldns 2>&1 | tail -1
kubectl -n kube-system rollout status ds/nodelocaldns --timeout=180s 2>&1 | tail -1
echo ""

echo "########## 3. 等 3 分钟验证 DNS 噪音消失 ##########"
sleep 180
echo -n "  nodelocaldns 错误（最近2分钟）: "
kubectl -n logging exec loki-0 -c loki -- wget -qO- \
  'http://localhost:3100/loki/api/v1/query?query=sum(count_over_time(%7Bnamespace%3D%22kube-system%22%2Cpod%3D~%22nodelocaldns.*%22%7D%20%7C~%20%22(?i)error%7Ctimeout%22%20%5B2m%5D))' 2>/dev/null | head -c 120; echo ""
echo -n "  coreDNS 错误（最近2分钟）: "
kubectl -n logging exec loki-0 -c loki -- wget -qO- \
  'http://localhost:3100/loki/api/v1/query?query=sum(count_over_time(%7Bnamespace%3D%22kube-system%22%2Cpod%3D~%22coredns.*%22%7D%20%7C~%20%22(?i)error%22%20%5B2m%5D))' 2>/dev/null | head -c 120; echo ""
echo ""

echo "########## 4. 燃烧告警排查（为何又出现）##########"
PP="prometheus-prometheus-stack-kube-prom-prometheus-0"
q() { kubectl -n monitoring exec $PP -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$1" 2>/dev/null; }
echo "--- firing 详情（哪个窗口）"
kubectl -n monitoring exec alertmanager-prometheus-stack-kube-prom-alertmanager-0 -c alertmanager -- \
  wget -qO- 'http://localhost:9093/api/v2/alerts?active=true&silenced=false' 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
for a in d:
    if "Burn" in (a["labels"].get("alertname") or ""):
        print("  [%s] long=%s short=%s since=%s" % (a["labels"].get("severity"),
              a["labels"].get("long"), a["labels"].get("short"), a.get("startsAt","")[:19]))
'
echo "--- 近30分钟 5xx 明细"
q "topk%2810%2Csum%20by%20%28code%2Cverb%29%20%28rate%28apiserver_request_total%7Bcode%3D~%225..%22%7D%5B30m%5D%29%29%29" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)["data"]["result"]
    if not d: print("  ✅ 近30分钟无 5xx（告警是长窗口在消化早前的错误）")
    for r in d: print("  code=%s %-8s %.3f/s" % (r["metric"].get("code"), r["metric"].get("verb"), float(r["value"][1])))
except Exception as e: print("  失败", e)
'
echo "--- 近30分钟 429 明细"
q "topk%285%2Csum%20by%20%28verb%29%20%28rate%28apiserver_request_total%7Bcode%3D%22429%22%7D%5B30m%5D%29%29%29" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)["data"]["result"]
    if not d: print("  ✅ 无 429")
    for r in d: print("  429 %-8s %.3f/s" % (r["metric"].get("verb"), float(r["value"][1])))
except Exception as e: print("  失败", e)
'
echo ""
echo "--- etcd 稳态复查（恢复 2500/250 后）"
for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
  echo -n "  [$ip] 慢写(10min)="; ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
    'journalctl -u etcd --since "10 minutes ago" 2>/dev/null | grep -c "slow fdatasync"' 2>/dev/null
done