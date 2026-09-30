#!/bin/bash
cd /tmp
python3 - <<'PYEOF'
import urllib.request
url = "http://127.0.0.1:9999/assets/js/auth-1hlkkF3R.js"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=20) as r:
    data = r.read()
open("/tmp/auth.js", "wb").write(data)
print("saved", len(data))
PYEOF
echo "=== authMethod 上下文 ==="
grep -o -E '.{60}authMethod.{100}' /tmp/auth.js | head -10
echo "=== 枚举/方式 ==="
grep -o -E 'authMethod[:=]"?[a-zA-Z_]*"?|"[a-z]*otp[a-z]*"|"webauthn"|"password"|authMethod' /tmp/auth.js | sort -u | head -20
echo "=== 登录请求体构造 ==="
grep -o -E '.{50}(login|Login).{100}' /tmp/auth.js | grep -iE 'authMethod|password|name' | head -10
