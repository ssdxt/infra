#!/bin/bash
H=harbor.wuxing.local
HP='<HARBOR_PASSWORD>'
ACCEPT='application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json'
echo "=== nginx:latest 现在的 Content-Type 和 digest ==="
curl -sk -u admin:$HP -o /dev/null -D - -H "Accept: $ACCEPT" "https://$H/v2/library/nginx/manifests/latest" 2>/dev/null | grep -iE 'HTTP/|content-type|docker-content-digest'
echo ""
echo "=== nginx 的所有 tag（确认没多出 -amd64/-arm64 之类）==="
curl -sk -u admin:$HP "https://$H/v2/library/nginx/tags/list" 2>/dev/null; echo
echo ""
echo "=== 用 Harbor API 看 tag 详情（架构字段）==="
curl -sk -u admin:$HP "https://$H/api/v2.0/projects/library/repositories/nginx/artifacts?page_size=10&with_tag=true" 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
for a in d:
    tags = [t["name"] for t in (a.get("tags") or [])]
    print("  digest:", a.get("digest","")[:25])
    print("   mediaType:", a.get("manifest_media_type"))
    print("   tags:", tags)
    print("   size(MB):", round((a.get("size") or 0)/1048576, 1))
    print("   push_time:", a.get("push_time"))
'
echo ""
echo "=== 对比：一个正常的多架构仓库（cilium）==="
curl -sk -u admin:$HP -o /dev/null -D - -H "Accept: $ACCEPT" "https://$H/v2/cilium/cilium/manifests/v1.20.1" 2>/dev/null | grep -i '^content-type'