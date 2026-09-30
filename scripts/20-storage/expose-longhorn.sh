#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "== 1. longhorn-frontend 暴露为 NodePort 30800 =="
kubectl -n longhorn-system patch svc longhorn-frontend \
  -p '{"spec":{"type":"NodePort","ports":[{"port":80,"targetPort":"http","nodePort":30800}]}}' 2>&1 | tail -1
sleep 2
kubectl -n longhorn-system get svc longhorn-frontend -o wide | sed 's/^/  /'
echo ""
echo -n "  本机验证 http://10.100.10.10:30800 : "
curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://10.100.10.10:30800/ 2>/dev/null; echo ""
echo -n "  从 worker 验证 : "
ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.33 \
  "curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://10.100.10.33:30800/" 2>/dev/null; echo ""
echo ""
echo "== 2. Gateway 服务的 NodePort（为以后'域名不带端口'做准备）=="
kubectl -n gateway get svc 2>/dev/null | sed 's/^/  /'
echo ""
echo "== 3. 现有 HTTPRoute 清单（域名 → 服务）=="
kubectl -n gateway get httproute 2>/dev/null --no-headers | awk '{print "  "$1"  hosts:"$5}' 2>/dev/null
kubectl -n gateway get httproute -o json 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
for r in d["items"]:
    hs = ",".join(r["spec"].get("hostnames", []))
    backends = []
    for rule in r["spec"].get("rules", []):
        for b in rule.get("backendRefs", []):
            backends.append("%s.%s:%s" % (b["name"], b.get("namespace","同ns"), b["port"]))
    print("  %-22s hosts=%-42s → %s" % (r["metadata"]["name"], hs, ",".join(backends)))
'