#!/bin/bash
R=/data1/ssdxt
echo "############ CHECKLIST: fixes written back to /data1/ssdxt/ ############"

echo ""
echo "=== 1) tools/fix-chart-images.py (dual-prefix bug fix) ==="
grep -n "registry'\] = harbor" $R/tools/fix-chart-images.py
grep -n 'repository.\] = f"{project}/{name}"' $R/tools/fix-chart-images.py
echo "  backups:"; ls -1 $R/tools/ | grep bak

echo ""
echo "=== 2) images/mirror.sh (k8s-sidecar added) ==="
grep -n 'k8s-sidecar' $R/images/mirror.sh
echo "  backups:"; ls -1 $R/images/ | grep bak

echo ""
echo "=== 3) monitoring/01-metrics-server.sh (system:auth-delegator) ==="
grep -n -A4 'auth-delegator' $R/monitoring/01-metrics-server.sh | head -12
echo "  backups:"; ls -1 $R/monitoring/ | grep bak

echo ""
echo "=== 4) charts/ (3 added charts) ==="
ls -la $R/charts/*.tgz

echo ""
echo "=== 5) storage/crds/ (VolumeSnapshot CRDs) ==="
ls -la $R/storage/crds/
kubectl get crd 2>/dev/null | grep -c 'snapshot.storage.k8s.io' | sed 's/^/  installed CRDs: /'

echo ""
echo "=== 6) logging/03-grafana-loki-datasource.sh ==="
ls -la $R/logging/03-grafana-loki-datasource.sh
grep -n -E 'loki-datasource|grafana_datasource|rollout restart' $R/logging/03-grafana-loki-datasource.sh

echo ""
echo "=== 7) logging/02-alloy.sh final key lines ==="
grep -n -E 'mounts:|varlog|NODE_NAME|stage.cri|source     = "filename"|local.file_match|loki.source.file' $R/logging/02-alloy.sh
echo "  backups:"; ls -1 $R/logging/ | grep bak

echo ""
echo "############ FULL FILE LISTING of /data1/ssdxt/ ############"
find $R -type f -printf '%10s  %TY-%Tm-%Td %TH:%TM  %p\n' 2>/dev/null | sort -k4
echo ""
echo "--- totals ---"
echo "  files: $(find $R -type f | wc -l)   dirs: $(find $R -type d | wc -l)   backups(.bak.*): $(find $R -name '*.bak.*' | wc -l)"
