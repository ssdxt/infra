#!/bin/bash
# control-01 涓婏細瀹夎淇鐗?fix-chart-images.py + 鏀惧叆缂哄け鐨?charts + 鍚屾 mirror.sh 娓呭崟
set -u
R=/data1/ssdxt
TS=$(date +%m%d-%H%M%S)

echo "=== [1] 澶囦唤骞跺畨瑁呬慨姝ｇ増 fix-chart-images.py ==="
cp -a $R/tools/fix-chart-images.py $R/tools/fix-chart-images.py.bak.$TS
echo "  澶囦唤: $R/tools/fix-chart-images.py.bak.$TS"
cp /tmp/fix-chart-images-v2.py $R/tools/fix-chart-images.py
chmod +x $R/tools/fix-chart-images.py
python3 -c "import ast,sys; ast.parse(open('$R/tools/fix-chart-images.py').read()); print('  璇硶 OK')"
echo "  --- 鏂伴€昏緫鍏抽敭琛?---"
grep -n "registry'\] =" $R/tools/fix-chart-images.py

echo ""
echo "=== [2] 鏀惧叆 charts ==="
for f in longhorn-1.7.2.tgz loki-6.24.0.tgz alloy-0.12.0.tgz; do
  if [ -f $R/charts/$f ]; then echo "  宸插瓨鍦?涓嶅姩): $f"; else cp /tmp/$f $R/charts/; echo "  宸叉斁鍏? $f"; fi
done
ls -la $R/charts/

echo ""
echo "=== [3] 鍚屾 images/mirror.sh 娓呭崟锛堣ˉ k8s-sidecar锛?=="
cp -a $R/images/mirror.sh $R/images/mirror.sh.bak.$TS
python3 - <<'PY'
p='/data1/ssdxt/images/mirror.sh'
s=open(p).read()
new='kiwigrid/k8s-sidecar:1.28.0|logging/k8s-sidecar:1.28.0\n'
anchor='grafana/alloy:v1.7.0|logging/alloy:v1.7.0\n'
if 'k8s-sidecar' in s:
    print('  宸插瓨鍦紝璺宠繃')
elif anchor in s:
    open(p,'w').write(s.replace(anchor, anchor+new, 1))
    print('  宸叉彃鍏?k8s-sidecar')
else:
    print('  !! 鏈壘鍒伴敋鐐癸紝鏈慨鏀?)
PY
grep -n 'sidecar' $R/images/mirror.sh

echo ""
echo "=== [4] 鐢ㄤ慨姝ｇ増宸ュ叿 dry-run 涓変釜 chart 鐨勯暅鍍忔槧灏?==="
for c in longhorn longhorn-1.7.2 ; do :; done
python3 $R/tools/fix-chart-images.py $R/charts/longhorn-1.7.2.tgz longhorn harbor.wuxing.local /tmp/chk-longhorn.yaml
python3 $R/tools/fix-chart-images.py $R/charts/loki-6.24.0.tgz logging harbor.wuxing.local /tmp/chk-loki.yaml
python3 $R/tools/fix-chart-images.py $R/charts/alloy-0.12.0.tgz logging harbor.wuxing.local /tmp/chk-alloy.yaml
echo "  --- longhorn image.repository ---"
grep -E 'repository:' /tmp/chk-longhorn.yaml | head -15
echo "  --- loki image blocks ---"
grep -B2 -A2 'repository:' /tmp/chk-loki.yaml | grep -E 'registry:|repository:' | head -12
echo "  --- alloy image block ---"
sed -n '/^image:/,/^rbac:/p' /tmp/chk-alloy.yaml | head -8

echo ""
echo "=== [5] helm 鐗堟湰 ==="
helm version --short
