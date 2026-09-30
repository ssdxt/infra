#!/bin/bash
echo procs:
ps aux | grep -E 'skopeo|otel-mirror|curl' | grep -v grep
echo files:
ls -la /tmp/otel-mirror* /tmp/otel-run.sh 2>&1
echo logtail:
ls -la /tmp/otel-mirror.log 2>&1
wc -c /tmp/otel-mirror.log 2>&1
