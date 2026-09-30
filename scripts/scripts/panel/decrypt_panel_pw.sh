#!/bin/bash
echo "=== 从二进制提取 oneof 校验值 ==="
grep -a -oE 'oneof=[a-zA-Z ]+' /usr/local/bin/1panel 2>/dev/null | sort -u | head -30
echo
echo "=== 尝试 AES-128-ECB 解密 Password 字段 ==="
B64="azrHDtsU3BZBCM8IaPhFogo/vYCr8Oi2nJq6yY/X0vw="
KEY=$(python3 -c "print('DFJR3GZPIPJBhsvG'.encode().hex())")
echo "KEY_HEX=$KEY"
echo "$B64" | base64 -d > /tmp/pw.bin
wc -c /tmp/pw.bin
echo "--- no padding ---"
openssl enc -d -aes-128-ecb -K "$KEY" -nopad -in /tmp/pw.bin 2>&1 | xxd | head -5
echo "--- pkcs7 unpad attempt ---"
openssl enc -d -aes-128-ecb -K "$KEY" -in /tmp/pw.bin 2>&1 | head -5
echo
echo "=== bcrypt 模块是否可用 ==="
python3 -c "import bcrypt; print('bcrypt ok')" 2>&1
echo "=== 直接用 app.yaml 里给的凭据试前端密码RSA加密流程(取authMethod枚举后再说) ==="
grep -a -oE '"authMethod"[^,}]*' /usr/local/bin/1panel 2>/dev/null | head -5
