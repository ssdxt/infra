#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. PrometheusRule 里还有没有 kube-proxy 规则 ====="
kubectl -n monitoring get prometheusrule --no-headers 2>/dev/null | grep -i proxy | sed 's/^/  ❌ 仍存在: /' || echo "  ✅ 已无 kube-proxy 相关 PrometheusRule"
echo ""
echo "===== 2. ServiceMonitor 里还有没有 kube-proxy ====="
kubectl -n monitoring get servicemonitor --no-headers 2>/dev/null | grep -i proxy | sed 's/^/  ❌ 仍存在: /' || echo "  ✅ 已无 kube-proxy 相关 ServiceMonitor"
echo ""
echo "===== 3. helm 里实际生效的 values（关键！）====="
helm get values prometheus-stack -n monitoring 2>/dev/null | grep -iA3 -E 'kubeProxy' | sed 's/^/  /' || echo "  ⚠️ values 里没有 kubeProxy 配置 —— 说明 helm 没收到这个参数"
echo ""
echo "  --- helm 最近 3 次发布历史"
helm history prometheus-stack -n monitoring 2>/dev/null | tail -4 | sed 's/^/  /'
echo ""
echo "===== 4. Prometheus 里是否还加载着 KubeProxyDown 规则 ====="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/rules' 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)["data"]["groups"]
    hit = []
    for g in d:
        for r in g.get("rules", []):
            if "Proxy" in (r.get("name") or "") or "proxy" in (r.get("name") or ""):
                hit.append((g["name"], r.get("name"), r.get("state"), r.get("health"), (r.get("lastError") or "")[:60]))
    if hit:
        for gname, rname, state, health, err in hit:
            print("  ❌ 规则组=%s 规则=%s state=%s health=%s err=%s" % (gname, rname, state, health, err))
    else:
        print("  ✅ Prometheus 里已无 KubeProxyDown 规则")
    print("  （共加载 %d 个规则组）" % len(d))
except Exception as e:
    print("  查询失败:", e)
'
echo ""
echo "===== 5. Prometheus 抓取配置里还有没有 kube-proxy job ====="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/targets?state=active' 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)["data"]["activeTargets"]
jobs = sorted(set(t["labels"].get("job","?") for t in d))
print("  当前 job 列表:", ", ".join(jobs))
print("  含 kube-proxy 的 target 数:", sum(1 for t in d if "proxy" in t["labels"].get("job","")))
'
echo ""
echo "===== 6. Alertmanager 当前告警（完整）====="
kubectl -n monitoring exec alertmanager-prometheus-stack-kube-prom-alertmanager-0 -c alertmanager -- \
  wget -qO- 'http://localhost:9093/api/v2/alerts?active=true&silenced=false&inhibited=false' 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
if not d: print("  （无活跃告警）")
for a in d:
    l = a["labels"]
    print("  [%s] %-30s startsAt=%s" % (l.get("severity"), l.get("alertname"), a.get("startsAt","")[:19]))
'
echo ""
echo "  --- 包含已 resolved 的（Alertmanager 会把刚恢复的保留一段时间）"
kubectl -n monitoring exec alertmanager-prometheus-stack-kube-prom-alertmanager-0 -c alertmanager -- \
  wget -qO- 'http://localhost:9093/api/v2/alerts' 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
for a in d:
    l = a["labels"]
    if "Proxy" in (l.get("alertname") or ""):
        print("  %s status=%s updatedAt=%s" % (l.get("alertname"), a.get("status",{}).get("state"), a.get("updatedAt","")[:19]))
        print("     startsAt=%s endsAt=%s" % (a.get("startsAt","")[:19], a.get("endsAt","")[:19]))
'
echo ""
echo "===== 7. Prometheus 里 KubeProxyDown 表达式当前求值 ====="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=absent(up%7Bjob%3D%22kube-proxy%22%7D%20%3D%3D%201)' 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)["data"]["result"]
print("  absent(up{job=\"kube-proxy\"}==1) 当前值:", d[0]["value"][1] if d else "无结果(0)")
'