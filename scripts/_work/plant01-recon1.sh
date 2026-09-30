#!/bin/bash
echo "===== HOSTNAME / DATE ====="
hostname; date; uname -r
echo
echo "===== docker ps (all wxq) ====="
docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' | grep -i wxq
echo
echo "===== wxq-prometheus inspect: Image / Args / Cmd / Entrypoint ====="
docker inspect wxq-prometheus --format 'IMAGE={{.Config.Image}}'
docker inspect wxq-prometheus --format 'ENTRYPOINT={{json .Config.Entrypoint}}'
docker inspect wxq-prometheus --format 'CMD={{json .Config.Cmd}}'
docker inspect wxq-prometheus --format 'ARGS={{json .Args}}'
echo
echo "===== wxq-prometheus PortBindings ====="
docker inspect wxq-prometheus --format '{{json .HostConfig.PortBindings}}'
echo
echo "===== wxq-prometheus Mounts ====="
docker inspect wxq-prometheus --format '{{range .Mounts}}{{.Type}} | {{.Source}} -> {{.Destination}} | RW={{.RW}}{{"\n"}}{{end}}'
echo
echo "===== wxq-prometheus RestartPolicy / NetworkMode / Labels (compose?) ====="
docker inspect wxq-prometheus --format 'RESTART={{json .HostConfig.RestartPolicy}} NET={{.HostConfig.NetworkMode}}'
docker inspect wxq-prometheus --format '{{json .Config.Labels}}'
echo
echo "===== compose project labels on ALL wxq containers ====="
for c in $(docker ps -a --format '{{.Names}}' | grep -i wxq); do
  echo "--- $c"
  docker inspect "$c" --format '{{index .Config.Labels "com.docker.compose.project"}} | {{index .Config.Labels "com.docker.compose.project.config_files"}} | {{index .Config.Labels "com.docker.compose.project.working_dir"}} | svc={{index .Config.Labels "com.docker.compose.service"}}'
done
echo
echo "===== /data1/apps/wxq-plant01-monitor/ tree (2 levels) ====="
ls -la /data1/apps/wxq-plant01-monitor/ 2>&1
echo "--- prometheus subdir"
ls -la /data1/apps/wxq-plant01-monitor/prometheus/ 2>&1
echo "--- rules dir"
ls -la /data1/apps/wxq-plant01-monitor/prometheus/rules/ 2>&1
echo "--- targets dir"
ls -la /data1/apps/wxq-plant01-monitor/prometheus/targets/ 2>&1
echo
echo "===== find any compose files under /data1/apps ====="
find /data1/apps -maxdepth 4 -name 'docker-compose*.y*ml' -o -maxdepth 4 -name 'compose*.y*ml' 2>/dev/null | head -50
echo
echo "===== prometheus.yml content ====="
cat /data1/apps/wxq-plant01-monitor/prometheus/prometheus.yml 2>&1
echo
echo "===== disk space ====="
df -h /data1 2>&1
