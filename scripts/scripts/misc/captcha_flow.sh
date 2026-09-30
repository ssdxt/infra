#!/bin/bash
echo "=== 前置IV模式精确解密 ==="
KEY_HEX=$(python3 -c "print('DFJR3GZPIPJBhsvG'.encode().hex())")
python3 - <<'PYEOF'
import base64
raw = base64.b64decode("azrHDtsU3BZBCM8IaPhFogo/vYCr8Oi2nJq6yY/X0vw=")
open("/tmp/pw.bin","wb").write(raw)
print("bytes:", len(raw), "first block(IV) hex:", raw[:16].hex())
PYEOF
openssl enc -d -aes-128-cbc -K "$KEY_HEX" -iv "$(xxd -p -l 16 /tmp/pw.bin | tr -d '\n')" -in /tmp/pw.bin -nopad 2>/dev/null | xxd | head -3
echo
echo "=== 获取验证码并保存图片 ==="
python3 - <<'PYEOF'
import json, urllib.request, base64
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()
r = json.loads(get("http://127.0.0.1:9999/api/v1/auth/captcha"))
print("captcha resp:", r)
img = get("http://127.0.0.1:9999" + r["data"]["imagePath"])
open("/tmp/captcha.png","wb").write(img)
print("image bytes:", len(img))
print("captchaID:", r["data"]["captchaID"])
# 保存公钥供登录用
pub = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvpX6/5nYLnsXA1SIP1Xw
8Xq74YagRPlcv8FkpemosrYz/2lxJ2jrlswhl35XE7FY9FAPF7hEaX2tS6rsj6ja
JZ2L4t6BZL+KuyUztbdNjpWvtabdRh9zE7McpSr553Jn0gf7JXIz9VQObXD9HSAX
Wp36UfxBhi5pmVwuZS9QiHuIf0xCv39Qo95iegYBank+QMGexqky7DRwt19O6Vc7
qW8t8Za3InpMHvWvUcFxBzH+aD79ayZb3g8VVcVwqhEVyV1EGsuS7+lmYPxx89B3
skQ0WJGMkU1cPoKcx0HmiBrrkiLRo8sfFNt9KLEMTTRKONvdsddXwoubYQd5HLYU
kQIDAQAB
-----END PUBLIC KEY-----"""
open("/tmp/pub.pem","w").write(pub)
print("pubkey saved")
PYEOF
echo "=== RSA加密 admin 密码 ==="
echo -n "admin" | openssl pkeyutl -encrypt -pubin -inkey /tmp/pub.pem 2>/dev/null | base64 -w0
echo
