#!/bin/bash
H=harbor.wuxing.local
HP='<HARBOR_PASSWORD>'
ACCEPT='application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json'

check() {
  local repo="$1" tag="$2"
  local ct digest
  ct=$(curl -sk -u admin:$HP -o /dev/null -D - -H "Accept: $ACCEPT" "https://$H/v2/$repo/manifests/$tag" 2>/dev/null | grep -i '^content-type' | tr -d '\r' | awk '{print $2}')
  digest=$(curl -sk -u admin:$HP -o /dev/null -D - -H "Accept: $ACCEPT" "https://$H/v2/$repo/manifests/$tag" 2>/dev/null | grep -i '^docker-content-digest' | tr -d '\r' | awk '{print $2}')
  if echo "$ct" | grep -qE 'manifest.list|image.index'; then
    printf "  %-42s %-10s => 多架构列表 list/index\n" "$repo" "$tag"
  else
    # 单架构：取 config blob 看架构
    cfg=$(curl -sk -u admin:$HP -H "Accept: $ACCEPT" "https://$H/v2/$repo/manifests/$tag" 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get("config",{}).get("digest",""))' 2>/dev/null)
    if [ -n "$cfg" ]; then
      arch=$(curl -sk -u admin:$HP "https://$H/v2/$repo/blobs/$cfg" 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("architecture","?")+"/"+d.get("os","?"))' 2>/dev/null)
    else
      arch="无法解析"
    fi
    printf "  %-42s %-10s => 单架构 [%s]  <== 需修复\n" "$repo" "$tag" "$arch"
  fi
}

echo "=== 逐仓库检查架构类型"
check library/nginx latest
check library/haproxy latest
check library/busybox 1.38.0
check wxq-monitor/prometheus latest
check wxq-monitor/node-exporter latest
check wxq-otel/otelcol-contrib latest
check wxq-vm/victoria-metrics latest
check monitoring/prometheus v2.54.1
check cilium/cilium v1.20.1