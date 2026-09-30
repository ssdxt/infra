#!/bin/sh
set -e
docker exec wxq-prometheus sh -c '
cp /etc/prometheus/prometheus.yml /tmp/ok.yml
cp /tmp/ok.yml /tmp/t1.yml
printf "\nstorage:\n  tsdb:\n    out_of_order_time_window: 30m\n" >> /tmp/t1.yml
promtool check config /tmp/t1.yml && echo KEY1_OK
cp /tmp/ok.yml /tmp/t2.yml
printf "\nstorage:\n  tsdb:\n    outOfOrderTimeWindow: 30m\n" >> /tmp/t2.yml
promtool check config /tmp/t2.yml && echo KEY2_OK
'
