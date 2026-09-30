#!/bin/bash
echo "=== holaros-portal 日志 (tail 40) ==="
docker logs holaros-portal --tail 40 2>&1 | tail -40
echo
echo "=== 29000 license 端口是否在监听 ==="
ss -tlnp 2>/dev/null | grep 29000 || echo "29000 无监听!"
echo
echo "=== 谁在提供 29000 (licsrv) ==="
docker ps -a --format '{{.Names}} | {{.Image}} | {{.Ports}} | {{.Status}}' | grep -iE 'lic|29000' || echo "无 license 容器"
ls -la /data/licsrv 2>/dev/null || echo "/data/licsrv 不存在"
echo
echo "=== holaros-nginx /chat 路由 ==="
grep -rn -A8 'chat' /root/work/holaros/conf.d/ /etc/nginx/conf.d/ 2>/dev/null | head -40
