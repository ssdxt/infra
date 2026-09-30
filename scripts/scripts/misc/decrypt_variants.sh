#!/bin/bash
B64="azrHDtsU3BZBCM8IaPhFogo/vYCr8Oi2nJq6yY/X0vw="
KEY_STR="DFJR3GZPIPJBhsvG"
KEY_HEX=$(python3 -c "print('$KEY_STR'.encode().hex())")
echo "$B64" | base64 -d > /tmp/pw.bin
echo "ciphertext bytes: $(wc -c < /tmp/pw.bin)"
echo "KEY_HEX=$KEY_HEX"
KEYMD5=$(echo -n "$KEY_STR" | md5sum | cut -d' ' -f1)
KEYSHA16=$(echo -n "$KEY_STR" | sha256sum | cut -d' ' -f1 | cut -c1-32)
try() {
  desc="$1"; shift
  out=$(openssl enc -d "$@" -in /tmp/pw.bin 2>/dev/null | tr -d '\0')
  if [ -n "$out" ]; then echo "[$desc] => $out"; else echo "[$desc] => (解密失败/无输出)"; fi
}
try "ECB key=EncryptKey"        -aes-128-ecb -K "$KEY_HEX" -nopad
try "CBC key=EncryptKey IV=key" -aes-128-cbc -K "$KEY_HEX" -iv "$KEY_HEX" -nopad
try "CBC key=EncryptKey IV=0"   -aes-128-cbc -K "$KEY_HEX" -iv "00000000000000000000000000000000" -nopad
try "ECB key=MD5(EncryptKey)"   -aes-128-ecb -K "$KEYMD5" -nopad
try "ECB key=SHA256[:16]"       -aes-128-ecb -K "$KEYSHA16" -nopad
try "CBC key=SHA256[:16] IV=key"-aes-128-cbc -K "$KEYSHA16" -iv "$KEY_HEX" -nopad
echo
echo "=== 带PKCS7去填充再试 ==="
for combo in "-aes-128-ecb -K $KEY_HEX" "-aes-128-cbc -K $KEY_HEX -iv $KEY_HEX"; do
  echo "[$combo]"
  openssl enc -d $combo -in /tmp/pw.bin 2>/dev/null | xxd | head -3
done
