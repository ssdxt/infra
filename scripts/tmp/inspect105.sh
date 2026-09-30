#!/bin/bash
echo "== compose 工具版本 =="
docker-compose version 2>/dev/null | head -1
docker compose version 2>/dev/null | head -1
echo "== 运行容器归属 =="
for c in $(docker ps --format '{{.Names}}'); do
  docker inspect "$c" --format '{{.Name}} | proj={{index .Config.Labels "com.docker.compose.project"}} | wd={{index .Config.Labels "com.docker.compose.project.working_dir"}} | file={{index .Config.Labels "com.docker.compose.project.config_files"}} | restart={{.HostConfig.RestartPolicy.Name}}'
done
