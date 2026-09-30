#!/bin/bash
echo "--- status ---"
sudo docker ps --filter name=oceanbase-ce --format '{{.Names}} | {{.Status}} | {{.Ports}}'
echo
echo "--- logs tail ---"
sudo docker logs --tail 8 oceanbase-ce 2>&1
echo
echo "--- port listen ---"
ss -tlnp 2>/dev/null | grep -E ':(2881|2882)'
echo
echo "--- mysql probe ---"
sudo docker exec oceanbase-ce bash -c 'mysql -h127.0.0.1 -P2881 -uroot -p12345 -e "select version(); show databases;" 2>&1 | head -25'
echo
echo "--- restart policy ---"
sudo docker inspect oceanbase-ce --format 'RestartPolicy={{.HostConfig.RestartPolicy.Name}} Running={{.State.Running}} StartedAt={{.State.StartedAt}}'
