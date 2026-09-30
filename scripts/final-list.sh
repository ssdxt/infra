#!/bin/bash
echo "=== control-01 /data1/ssdxt/ 最终清单"
find /data1/ssdxt -maxdepth 2 -type f -printf '%-58p %8s bytes\n' 2>/dev/null | sort
echo ""
echo "=== 确认 gateway-api 目录已清爽"
ls -la /data1/ssdxt/charts/gateway-api/