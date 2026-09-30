#!/bin/bash
echo "--- functional SQL test via obclient inside container ---"
sudo docker exec oceanbase-ce obclient -h127.0.0.1 -P2881 -uroot -p12345 -e "select version(); show databases;" 2>&1 | head -25
echo "exit=$?"
echo
echo "--- log lines after the successful startup marker ---"
sudo docker logs oceanbase-ce 2>&1 | awk '/obshell program health check ok/{f=1} f' | tail -20
echo "(empty = nothing after success marker)"
echo
echo "--- listener owner ---"
sudo ss -tlnp 2>/dev/null | grep 2881
