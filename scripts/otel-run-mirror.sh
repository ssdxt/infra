#!/bin/bash
pkill -f 'bash /tmp/otel-mirror.sh' 2>/dev/null
sleep 1
bash /tmp/otel-mirror.sh > /tmp/otel-mirror.log 2>&1
echo "mirror_exit=$?"
grep -vE 'Copying|Awaiting|compression|digest|status:|Error' /tmp/otel-mirror.log | tail -25
echo "--- errors in log:"
grep -iE 'error|failed|FATA' /tmp/otel-mirror.log | tail -10
