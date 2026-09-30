#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf

echo "############ A. plant01 (10.100.10.29) 现有监控 ############"
timeout 30 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.29 '
echo "--- docker 容器（监控相关）"
docker ps --format "{{.Names}}\t{{.Image}}\t{{.Ports}}" 2>/dev/null | grep -iE "prometheus|grafana|alertmanager|victoria|thanos|vmagent" || echo "  无监控容器"
echo "--- 所有监听端口（9090/9093/3000/8428）"
ss -lntp 2>/dev/null | grep -E ":9090|:9093|:3000|:8428|:9091" || echo "  无相关端口"
echo "--- 是否有 Prometheus 数据目录"
ls -d /data1/*prometheus* /data1/*grafana* 2>/dev/null | head -5
' 2>/dev/null

echo ""
echo "############ B. plant02 (10.100.10.31) 作为 NFS 服务器评估 ############"
timeout 30 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.31 '
echo "--- 系统"
hostname; . /etc/os-release 2>/dev/null; echo "  $PRETTY_NAME"
echo "--- 磁盘"
df -h / /data1 2>/dev/null | tail -3
echo "--- 内存"
free -g | head -2
echo "--- 是否已装 NFS 服务端"
dpkg -l 2>/dev/null | grep -E "nfs-kernel-server" | head -2 || echo "  未安装"
systemctl is-active nfs-server 2>/dev/null || echo "  nfs-server 未运行"
echo "--- IP"
ip -4 addr show 2>/dev/null | grep -oE "inet 10\.100[0-9.]+"
echo "--- 已有导出"
cat /etc/exports 2>/dev/null | grep -v "^#" | head -5 || echo "  无导出配置"
' 2>/dev/null

echo ""
echo "############ C. 集群：容器指标 & 掉线检测能力 ############"
echo "--- ServiceMonitor（监控抓取配置）"
kubectl get servicemonitor -n monitoring --no-headers 2>/dev/null | awk '{print "  " $1}' | head -15
echo "--- kubelet/cAdvisor 是否被采集（容器级资源数据源）"
kubectl get servicemonitor -n monitoring --no-headers 2>/dev/null | grep -ci kubelet | xargs -I{} echo "  kubelet ServiceMonitor 数: {}"
echo "--- 掉线类告警规则是否存在"
kubectl get prometheusrule -n monitoring -o json 2>/dev/null | python3 -c '
import sys, json
try: d=json.load(sys.stdin)
except Exception: print("  读取失败"); raise SystemExit
hits=[]
for r in d["items"]:
    for g in r["spec"].get("groups",[]):
        for rule in g.get("rules",[]):
            a=rule.get("alert","")
            if any(k in a for k in ("NodeNotReady","NodeDown","KubeletDown","NodeReady","TargetDown","NodeNetwork")):
                hits.append(a)
print("  找到掉线/异常类告警:", len(hits))
for h in sorted(set(hits))[:12]: print("    -", h)
'
echo ""
echo "--- kube-vip 是否支持 LoadBalancer 服务（Gateway 分 IP 的前提）"
kubectl get cm -n kube-system 2>/dev/null | grep -i kube-vip
kubectl -n kube-system get pods -l app=kube-vip-ds -o jsonpath='{.items[0].spec.containers[0].env}' 2>/dev/null | python3 -c 'import sys,json; [print("   ",e.get("name"),"=",e.get("value")) for e in json.load(sys.stdin) if "svc" in (e.get("name") or "").lower() or "enable" in (e.get("name") or "").lower()]' 2>/dev/null
echo ""
echo "--- 现有 Gateway API 资源"
kubectl get gatewayclass 2>&1 | tail -1
kubectl get gateway,httproute -A 2>&1 | head -3
