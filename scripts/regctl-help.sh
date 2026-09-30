#!/bin/bash
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
H=harbor.wuxing.local
CREDS="admin:<HARBOR_PASSWORD>"

echo "===== A. regctl image index create 完整帮助 ====="
regctl image index create --help 2>&1 | sed -n '1,40p'
echo ""
echo "===== B. regctl image copy 完整帮助（看 platform 是否可重复）====="
regctl image copy --help 2>&1 | sed -n '1,40p'
