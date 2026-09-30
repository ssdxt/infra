#!/bin/bash
cd /tmp
echo "=== auth.js 内容 ==="
cat /tmp/auth.js
echo
echo "=== 二进制中 oneof 标签 ==="
grep -a -oE 'oneof=[a-zA-Z_ ]+' /usr/local/bin/1panel | sort -u | head -20
echo "=== 二进制中 webauthn/otp/authMethod ==="
for pat in webauthn authMethod "AuthMethod" totp; do
  echo -n "$pat: "; grep -a -o "$pat" /usr/local/bin/1panel | wc -l
done
echo "=== 下载全部 chunk 并扫 authMethod ==="
python3 - <<'PYEOF'
import urllib.request, re, os
base = "http://127.0.0.1:9999/assets/js/"
main = open("/tmp/panel.js", encoding="utf-8", errors="ignore").read()
chunks = sorted(set(re.findall(r'assets/js/[A-Za-z0-9_.-]+\.js', main)))
print("total chunks:", len(chunks))
for c in chunks:
    fn = "/tmp/chunks/" + os.path.basename(c)
    os.makedirs("/tmp/chunks", exist_ok=True)
    if not os.path.exists(fn):
        try:
            req = urllib.request.Request(base + os.path.basename(c), headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                open(fn, "wb").write(r.read())
        except Exception as e:
            print("ERR", c, e)
PYEOF
echo "=== 扫描结果 ==="
grep -l -E 'authMethod' /tmp/chunks/*.js 2>/dev/null
for f in $(grep -l -E 'authMethod' /tmp/chunks/*.js 2>/dev/null); do
  echo "--- $f ---"
  grep -o -E '.{50}authMethod.{120}' "$f" | head -6
done
