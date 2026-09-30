#!/bin/bash
for i in $(seq 1 150); do
  pgrep -f 'skopeo copy' >/dev/null || break
  sleep 15
done
echo MIRROR_FINISHED
tr '\r' '\n' < /tmp/otel-mirror.log | grep -vE 'Copying|Awaiting|^$' | tail -20
