#!/bin/bash
echo "=== 修复 RSA 加密测试 ==="
printf 'admin' > /tmp/pw.txt
openssl pkeyutl -encrypt -pubin -inkey /tmp/pub.pem -in /tmp/pw.txt -out /tmp/pw.enc 2>&1 | head -3
echo "rc=$?"
if [ -f /tmp/pw.enc ]; then base64 -w0 /tmp/pw.enc; echo; fi
echo "=== 获取新验证码并保存图片 ==="
python3 - <<'PYEOF'
import json, urllib.request, base64
req = urllib.request.Request("http://127.0.0.1:9999/api/v1/auth/captcha", headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10) as r:
    data = json.loads(r.read().decode())
cid = data["data"]["captchaID"]
b64img = data["data"]["imagePath"].split(",", 1)[1]
img = base64.b64decode(b64img)
open("/tmp/captcha.png", "wb").write(img)
open("/tmp/cid.txt", "w").write(cid)
print("captchaID:", cid)
print("img_len:", len(img))
PYEOF
echo "=== 图片base64(前若干) ==="
base64 -w0 /tmp/captcha.png
