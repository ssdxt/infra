#!/bin/bash
D=/data1/apps/wxq-plant01-monitor
cd $D || exit 1

echo "########## 1. compose 文件 ##########"
ls -la $D/docker-compose* 2>/dev/null
echo ""
cat docker-compose.yaml 2>/dev/null || echo "（没有 docker-compose.yaml）"

echo ""
echo "########## 2. 语法校验 ##########"
docker compose config -q 2>&1 | head -12
echo "退出码: $?"

echo ""
echo "########## 3. 运行中容器（含 compose 服务名）##########"
for c in $(docker ps -a --format '{{.Names}}' | sort); do
  svc=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' $c 2>/dev/null)
  proj=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' $c 2>/dev/null)
  [ -n "$svc" ] && printf "  %-26s svc=%-22s proj=%s\n" "$c" "$svc" "$proj"
done

echo ""
echo "########## 4. 各容器运行事实 ##########"
for c in $(docker ps -a --format '{{.Names}}' | sort); do
  svc=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' $c 2>/dev/null)
  [ -z "$svc" ] && continue
  echo "=== $c  (svc=$svc)"
  docker inspect -f '  镜像: {{.Config.Image}}
  命令: {{.Config.Entrypoint}} {{.Config.Cmd}}
  参数: {{.Args}}
  重启: {{.HostConfig.RestartPolicy.Name}}
  端口: {{range $p, $b := .HostConfig.PortBindings}}{{$p}}->{{range $b}}{{.HostPort}}{{end}} {{end}}
  网络: {{range $k,$v := .NetworkSettings.Networks}}{{$k}}[aliases:{{range $v.Aliases}}{{.}} {{end}}] {{end}}
  卷: {{range .Mounts}}{{if eq .Type "bind"}}{{.Source}}:{{.Destination}} {{else}}VOL:{{.Name}}:{{.Destination}} {{end}}{{end}}' $c 2>/dev/null
  echo ""
done