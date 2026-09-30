#!/bin/bash
D=/data1/apps/wxq-plant01-monitor
echo "========== 1. 目录现状 =========="
ls -la $D/ 2>/dev/null | head -20
echo "--- 所有 compose 相关文件（含隐藏）"
find $D/ -maxdepth 2 -iname '*compose*' -exec ls -la {} \; 2>/dev/null
echo ""
echo "========== 2. 运行中的容器 + 它们的 compose 标签 =========="
printf "  %-28s %-22s %-22s %s\n" "容器名" "compose服务名" "compose项目" "镜像"
for c in $(docker ps -a --format '{{.Names}}' | sort); do
  svc=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' $c 2>/dev/null)
  proj=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' $c 2>/dev/null)
  img=$(docker inspect -f '{{.Config.Image}}' $c 2>/dev/null)
  printf "  %-28s %-22s %-22s %s\n" "$c" "${svc:--}" "${proj:--}" "$img"
done
echo ""
echo "========== 3. compose 标签里记录的【原始文件路径】 =========="
docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' $(docker ps -q | head -1) 2>/dev/null
docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' $(docker ps -q | head -1) 2>/dev/null
echo ""
echo "========== 4. 如果 compose 文件已存在，做校验 =========="
cd $D
if [ -f docker-compose.yaml ]; then
  echo "  ✅ 文件存在（$(stat -c '%s bytes, mtime=%y' docker-compose.yaml)）"
  echo "--- 语法校验"
  docker compose config -q 2>&1 | head -8 && echo "  语法 OK" || echo "  语法有问题（见上）"
  echo "--- 文件里定义的服务"
  docker compose config --services 2>/dev/null | sed 's/^/    /'
  echo "--- compose ps（看它认不认现有容器）"
  docker compose ps -a --format 'table {{.Service}}\t{{.Name}}\t{{.State}}' 2>&1 | head -15
elif [ -f docker-compose.yaml.bak ] || ls $D/docker-compose* >/dev/null 2>&1; then
  echo "  找到这些 compose 文件："; ls -la $D/docker-compose* 2>/dev/null
else
  echo "  ❌ 仍然没有 docker-compose.yaml"
fi
echo ""
echo "========== 5. 各容器关键事实（重建/比对用）=========="
for c in wxq-prometheus wxq-alertmanager wxq-grafana wxq-prometheusalert wxq-victoriametrics; do
  if docker inspect $c >/dev/null 2>&1; then
    echo "=== $c"
    docker inspect -f '  镜像: {{.Config.Image}}
  参数: {{.Args}}
  重启: {{.HostConfig.RestartPolicy.Name}}
  端口: {{range $p, $b := .HostConfig.PortBindings}}{{$p}}->{{range $b}}{{.HostPort}}{{end}} {{end}}
  网络: {{range $k,$v := .NetworkSettings.Networks}}{{$k}}[{{range $v.Aliases}}{{.}} {{end}}] {{end}}
  卷: {{range .Mounts}}{{.Source}}:{{.Destination}} {{end}}' $c 2>/dev/null
  fi
done