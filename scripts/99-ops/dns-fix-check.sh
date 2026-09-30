#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== operator 最新日志-gateway 相关"
kubectl logs -n kube-system -l io.cilium/app=operator --tail=200 2>/dev/null | grep -iE 'gateway|kube-proxy-replacement|warn|error' | tail -6
echo "=== operator 是否已重启（拿新配置）"
kubectl get pods -n kube-system -l io.cilium/app=operator --no-headers 2>&1 | awk '{print $1, $2, $3, $5}'
echo "=== Harbor 是否有 nodelocaldns 镜像"
curl -sk -u admin:<HARBOR_PASSWORD> 'https://harbor.wuxing.local/api/v2.0/search?q=node-cache' 2>/dev/null | head -c 400; echo
echo "=== Harbor 里 dns 相关项目"
curl -sk -u admin:<HARBOR_PASSWORD> 'https://harbor.wuxing.local/v2/_catalog?n=200' 2>/dev/null | python3 -c 'import sys,json; print([r for r in json.load(sys.stdin).get("repositories",[]) if "dns" in r.lower() or "cache" in r.lower()])' 2>/dev/null
echo "=== 节点 kubelet clusterDNS 当前值"
timeout 15 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.33 'grep -A2 clusterDNS /var/lib/kubelet/config.yaml' 2>/dev/null
echo "=== kk artifact 里是否有 nodelocaldns 清单"
ls /data1/kubekey/package-ssdxt/ 2>/dev/null | head -5