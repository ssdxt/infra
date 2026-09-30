#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. kube-vip logs mentioning 10.100.10.252 ====="
for p in $(kubectl -n kube-system get pod -o name | grep kube-vip); do echo "--- $p ---"; kubectl -n kube-system logs $p --tail=400 2>&1 | grep -E '252|test-lb|adding|service' | tail -20; done
echo
echo "===== 2. le-svc / ip addr (kube-ipvs0, dummy) ====="
ip -o addr show | grep -E 'kube-ipvs0|10.100.10.25|10.100.10.250|10.100.10.252' || echo "(no 25x addr besides primary)"
echo
echo "--- ipvsadm -Ln (service VIPs) ---"
which ipvsadm >/dev/null 2>&1 && ipvsadm -Ln 2>&1 | head -40 || echo "(ipvsadm not installed)"
echo
echo "===== 3. connectivity to 10.100.10.252 from control-01 ====="
ping -c 2 -W 2 10.100.10.252 2>&1 | tail -4
echo "--- curl 10.100.10.252 ---"
curl -s -o /dev/null -w 'http_code=%{http_code}\n' --max-time 5 -H 'Host: grafana.wuxing.local' http://10.100.10.252/login || echo "(curl failed rc=$?)"
echo
echo "===== 4. lease holders (who is svcs leader) ====="
kubectl -n kube-system get lease plndr-svcs-lock plndr-cp-lock -o jsonpath='{range .items[*]}{.metadata.name}{" holder="}{.spec.holderIdentity}{" renew="}{.spec.renewTime}{"\n"}{end}'
echo
echo "===== 5. reference doc: all chapter headings ====="
grep -nE '^#{1,3} ' /data1/ssdxt/集群改造详细命令记录.md | head -60
echo
echo "===== 6. reference doc: kube-vip / LB sections ====="
grep -n -iE 'kube-vip|svc_enable|vip_pool|LoadBalancer|lb_enable|IP 池|IP池' /data1/ssdxt/集群改造详细命令记录.md | head -60
