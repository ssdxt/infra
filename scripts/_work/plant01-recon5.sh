#!/bin/bash
echo "===== network config of wxq-prometheus ====="
docker inspect wxq-prometheus --format '{{json .NetworkSettings.Networks}}' | python3 -m json.tool
echo
echo "===== all wxq containers: network aliases + IPs on wxq-monitor ====="
for c in $(docker ps -a --format '{{.Names}}' | grep -i wxq); do
  echo "--- $c"
  docker inspect "$c" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}: IP={{$v.IPAddress}} aliases={{$v.Aliases}} links={{$v.Links}}{{"\n"}}{{end}}'
done
echo
echo "===== does 'prometheus' DNS name resolve from alertmanager/vm? ====="
docker exec wxq-alertmanager getent hosts prometheus 2>&1
docker exec wxq-victoriametrics getent hosts prometheus 2>&1
echo
echo "===== prometheus container ExtraHosts / Dns / Hostname ====="
docker inspect wxq-prometheus --format 'hostname={{.Config.Hostname}} domainname={{.Config.Domainname}} extrahosts={{.HostConfig.ExtraHosts}} dns={{.HostConfig.Dns}} logdriver={{.HostConfig.LogConfig.Type}}'
echo
echo "===== prometheus full volume list incl. type/name ====="
docker inspect wxq-prometheus --format '{{json .HostConfig.Mounts}}' | python3 -m json.tool
echo
echo "===== volume wxq-monitor_prometheus-data: size / in-use? ====="
docker volume inspect wxq-monitor_prometheus-data
du -sh /data1/docker/volumes/wxq-monitor_prometheus-data/_data 2>/dev/null
echo
echo "===== node-exporter mount check for process-exporter config path ====="
docker inspect wxq-process-exporter --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
echo
echo "===== free disk ====="
df -h /var/lib/docker /data1 2>&1
