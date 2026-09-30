#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
H=harbor.wuxing.local
HP='<HARBOR_PASSWORD>'
echo "=== Harbor 全部仓库（catalog）"
curl -sk -u admin:$HP "https://$H/v2/_catalog?n=500" 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  共", len(d.get("repositories",[])), "个仓库"); [print("   ",r) for r in sorted(d.get("repositories",[]))]' 2>/dev/null
echo ""
echo "=== library/nginx 存在吗？有哪些 tag？"
curl -sk -u admin:$HP "https://$H/v2/library/nginx/tags/list" 2>/dev/null; echo
echo ""
echo "=== nginx:latest 的 manifest 类型（判断是单架构还是多架构列表）"
curl -sk -u admin:$HP -o /dev/null -D - -H 'Accept: application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json' "https://$H/v2/library/nginx/manifests/latest" 2>/dev/null | grep -iE 'HTTP/|content-type|docker-content-digest'
echo ""
echo "=== 如果存在，列出它包含的架构"
curl -sk -u admin:$HP -H 'Accept: application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.index.v1+json' "https://$H/v2/library/nginx/manifests/latest" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
except Exception as e:
    print("  非 manifest list（单架构镜像或不存在）"); raise SystemExit
if "manifests" in d:
    print("  类型: manifest list / index")
    for m in d["manifests"]:
        p=m.get("platform",{})
        print(f"    {p.get(\"os\",\"?\"):8s} {p.get(\"architecture\",\"?\"):8s} {m.get(\"digest\",\"\")[:30]}")
else:
    print("  类型: 单个 image manifest（单架构）")
    print("  config mediaType:", d.get("config",{}).get("mediaType"))
'