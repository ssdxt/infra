#!/bin/bash
for f in \
  /root/apps/docker/holarfileparse/docker-compose.yml \
  /root/asr_work/holarasr_online/docker-compose.yml \
  /root/apps/docker/holarchat/docker-compose.yml \
  /opt/1panel/apps/local/holarkanban/HolarKanban/docker-compose.yml \
  /opt/1panel/apps/local/holartts/holartts/docker-compose.yml ; do
  echo "###### FILE: $f"
  cat "$f"
  echo
done
