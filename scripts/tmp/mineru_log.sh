#!/bin/bash
C=$(docker ps --format '{{.Names}}' | grep mineru | head -1)
echo "CONTAINER=$C"
docker logs "$C" --tail 25 2>&1 | tail -25
