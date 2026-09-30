#!/bin/bash
FILES="\
/root/apps/docker/holarfileparse/docker-compose.yml \
/root/sherpa/docker/docker-compose.yml \
/root/embed/docker-compose-embed.yml \
/root/llm/docker_2/mineru_2509_1.2b/docker-compose.yml \
/root/asr_work/holarasr_online/docker-compose.yml \
/root/asr_work/docker/docker-compose.yml \
/data/aippt/docker-compose.yml \
/root/apps/docker/holarchat/docker-compose.yml \
/opt/1panel/apps/local/holaros/holaros/docker-compose.yml \
/root/work/holarvm/docker-compose.yml \
/root/work/docker-compose-deepdoc.yml \
/opt/1panel/apps/local/holarkanban/HolarKanban/docker-compose.yml \
/root/work/docker-compose-oneapi.yml \
/opt/1panel/apps/local/holartts/holartts/docker-compose.yml \
/root/work/docker-compose-database.yaml"
for f in $FILES; do
  echo "###### FILE: $f"
  awk '
    /^  [A-Za-z0-9_.-]+:[[:space:]]*($|#)/ {print "SVC " $0; next}
    /^    image:/ {print "    " $0; next}
    /^    container_name:/ {print "    " $0; next}
    /^    gpus:/ {print "    " $0; in_gpus=1; next}
    in_gpus && /^      / {print "    " $0; next}
    /^    runtime:/ {print "    " $0; next}
    /^    ports:/ {print "    " $0; in_ports=1; next}
    in_ports && /^      - / {print "    " $0; next}
    in_ports && !/^      / {in_ports=0}
    /^    command:/ {print "    " substr($0,1,120); next}
  ' "$f"
  echo
done
