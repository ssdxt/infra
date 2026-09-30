#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. prometheus-adapter 现状 ====="
kubectl -n monitoring get pods | grep adapter | sed 's/^/  /'
echo -n "  APIService: "
kubectl get apiservice v1beta1.custom.metrics.k8s.io -o jsonpath='{.status.conditions[0].type}={.status.conditions[0].status}{"\n"}' 2>/dev/null
echo ""
echo "--- 最近崩溃原因"
kubectl -n monitoring get pods -o json 2>/dev/null | python3 -c '
import sys, json, datetime
d = json.load(sys.stdin)
now = datetime.datetime.now(datetime.timezone.utc)
for p in d["items"]:
    if "adapter" not in p["metadata"]["name"]: continue
    print("  Pod:", p["metadata"]["name"])
    for cs in p["status"].get("containerStatuses", []):
        print("    restartCount =", cs.get("restartCount"))
        lt = (cs.get("lastState") or {}).get("terminated") or {}
        if lt:
            print("    上次退出:", lt.get("reason"), "exit=", lt.get("exitCode"), "at", str(lt.get("finishedAt"))[:19])
        rd = cs.get("ready"); print("    ready =", rd)
'
echo ""
echo -n "  实时资源占用: "
kubectl -n monitoring top pods 2>/dev/null | grep adapter | tr '\n' ' ' | sed 's/^/  /'; echo ""
echo ""
echo "===== 2. hubble-relay OOM 详情 ====="
kubectl -n kube-system get deploy hubble-relay -o jsonpath='副本={.spec.replicas} 资源={.spec.template.spec.containers[0].resources}{"\n"}' 2>/dev/null
kubectl -n kube-system get pods | grep hubble-relay | sed 's/^/  /'
echo -n "  创建时间/是谁装的: "
kubectl -n kube-system get deploy hubble-relay -o jsonpath='{.metadata.creationTimestamp}  labels={.metadata.labels}{"\n"}' 2>/dev/null
echo ""
echo "===== 3. 最近 10 分钟 apiserver 错误是否还在持续（Loki 复核）====="
kubectl -n logging exec loki-0 -c loki -- wget -qO- \
  'http://localhost:3100/loki/api/v1/query?query=sum(count_over_time(%7Bnamespace%3D%22kube-system%22%2Cpod%3D~%22kube-apiserver.*%22%7D%20%7C~%20%22(?i)error%22%20%5B5m%5D))' 2>/dev/null | head -c 200; echo ""
echo ""
echo "===== 4. 当前燃烧告警窗口详情 ====="
kubectl -n monitoring exec alertmanager-prometheus-stack-kube-prom-alertmanager-0 -c alertmanager -- \
  wget -qO- 'http://localhost:9093/api/v2/alerts?active=true&silenced=false' 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
for a in d:
    if a["labels"].get("alertname") == "KubeAPIErrorBudgetBurn":
        print("  [%s] long=%s short=%s since=%s" % (a["labels"].get("severity"), a["labels"].get("long"), a["labels"].get("short"), a.get("startsAt","")[:19]))
'