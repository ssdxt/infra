#!/bin/bash
cd /tmp
python3 - <<'PYEOF'
import urllib.request
url = "http://127.0.0.1:9999/assets/js/index-BnHAZy77.js"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=20) as r:
    data = r.read()
open("/tmp/panel.js", "wb").write(data)
print("saved", len(data))
PYEOF
echo "=== authMethod 上下文 ==="
grep -o -E '.{50}authMethod.{80}' /tmp/panel.js | head -8
echo "=== 可能的枚举值 ==="
grep -o -E '"authMethod":"[a-z]+"|authMethod:"[a-z]+"|authMethod=.[a-z]+.|[a-z]*otp[a-z]*|webauthn|totp|twofactor|mfa' /tmp/panel.js | sort -u | head -20
echo "=== login 请求构造 ==="
grep -o -E '.{40}/auth/login.{60}' /tmp/panel.js | head -5
