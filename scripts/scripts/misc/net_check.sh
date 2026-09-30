#!/bin/bash
echo "=== 当前所有网络及子网 ==="
for n in $(docker network ls -q); do
  name=$(docker network inspect "$n" --format '{{.Name}}' 2>/dev/null)
  subnet=$(docker network inspect "$n" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null)
  used=$(docker network inspect "$n" --format '{{len .Containers}}' 2>/dev/null)
  printf "%-35s %-18s 容器数:%s\n" "$name" "$subnet" "$used"
done
echo
echo "=== 是否有配置引用 172.18.0.x (迁移需注意) ==="
grep -rn '172\.18\.0\.' /root/work /root/apps /data /opt/1panel/apps 2>/dev/null --include='*.conf' --include='*.yaml' --include='*.yml' --include='*.json' --include='*.env' | head -10
echo "--- 引用检查完成 ---"
