#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "############ 1. plant01 Prometheus 是否支持 remote_write 接收（关键前提）############"
timeout 30 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.29 '
echo "--- Prometheus 启动命令/参数"
docker inspect wxq-prometheus --format "{{.Args}}" 2>/dev/null
echo "--- 是否有 remote-write-receiver 标志"
docker inspect wxq-prometheus --format "{{.Args}}" 2>/dev/null | grep -o "web.enable-remote-write-receiver" || echo "  !! 未开启 remote-write-receiver"
echo "--- 挂载的配置文件"
docker inspect wxq-prometheus --format "{{range .Mounts}}{{.Source}} -> {{.Destination}}{{\"\n\"}}{{end}}" 2>/dev/null | head -6
echo "--- 配置目录"
ls -la /data1/*prometheus*/ /data1/wxq-monitor*/ 2>/dev/null | head -12
' 2>/dev/null

echo ""
echo "############ 2. 集群节点是否有 NFS 客户端（挂 NFS PV 的前提）############"
for ip in 10.100.10.10 10.100.10.33 10.100.10.47; do
  echo -n "  $ip: "
  timeout 15 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip 'dpkg -l 2>/dev/null | grep -q nfs-common && echo "nfs-common 已装" || echo "需安装 nfs-common"; which mount.nfs 2>/dev/null || true' 2>/dev/null
done

echo ""
echo "############ 3. kube-vip 的 LoadBalancer 能力 ############"
kubectl get ds -n kube-system 2>/dev/null | grep -i vip
kubectl -n kube-system get ds kube-vip-ds -o json 2>/dev/null | python3 -c '
import sys, json
try: d=json.load(sys.stdin)
except Exception: print("  读取失败"); raise SystemExit
for c in d["spec"]["template"]["spec"]["containers"]:
    for e in c.get("env", []) or []:
        n=e.get("name","")
        if "svc" in n.lower() or "VIP" in n or "enable" in n.lower():
            print("   ", n, "=", e.get("value"))
' 2>/dev/null
echo "--- 现有 LoadBalancer 类型 Service"
kubectl get svc -A --no-headers 2>/dev/null | awk '$3=="LoadBalancer"{print "  " $1, $2, $5, $6}' | head -5 || echo "  无"
echo ""
echo "############ 4. 当前存储类 ############"
kubectl get storageclass 2>&1
echo "--- 集群里已用的 PVC"
kubectl get pvc -A --no-headers 2>/dev/null | head -5 || echo "  无 PVC"
