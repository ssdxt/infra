#!/bin/bash
echo "########## 1. 三个服务状态 ##########"
for s in chat_doc_api chat_doc_web chat_doc_speech; do
  printf "  %-20s %s\n" "$s" "$(systemctl is-active $s 2>&1)"
done

echo
echo "########## 2. API 端口实际响应 ##########"
echo "--- 8261 /docs ---"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -m 10 http://127.0.0.1:8261/docs
echo "--- 8261 /v1/models ---"
curl -s -m 10 http://127.0.0.1:8261/v1/models 2>&1 | head -c 300
echo
echo "--- 3333 (web) ---"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -m 10 http://127.0.0.1:3333/

echo
echo "########## 3. 最近的错误（过滤已知无害告警）##########"
journalctl -u chat_doc_api -b --no-pager -o cat 2>/dev/null \
  | grep -iE "error|traceback|exception|failed" \
  | grep -viE "Please use PaddlePaddle with GPU|Ultralytics|Settings reset|pytree_node" \
  | tail -10
echo "(以上为空=无实质错误)"

echo
echo "########## 4. 环境健康复核（还有没有混装）##########"
python3 - <<'EOF'
import os, re, collections
PKG="/root/anaconda3/envs/recovery/lib/python3.8/site-packages"
pat=re.compile(r"^(?P<name>.+?)-(?P<ver>\d[^-]*)\.dist-info$")
g=collections.defaultdict(list)
for d in os.listdir(PKG):
    m=pat.match(d)
    if m: g[m.group("name").lower().replace("_","-")].append(m.group("ver"))
dups={k:v for k,v in g.items() if len(v)>1}
print(f"  多版本 dist-info 的包: {len(dups)}")
EOF

echo
echo "########## 5. 备份位置与大小 ##########"
BK=/deploy/cc/logs/pkg-backup-20260914-093505
du -sh $BK 2>/dev/null
echo "  files/: $(find $BK/mixed-cleanup/files -type f 2>/dev/null | wc -l) 个文件"
echo "  dists/: $(ls $BK/mixed-cleanup/dists 2>/dev/null | wc -l) 个 dist-info"
