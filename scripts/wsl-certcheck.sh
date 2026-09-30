#!/bin/bash
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
echo "===== 1. 我保存的 harbor-ca.crt 是什么 ====="
openssl x509 -in "/mnt/c/Users/CC/Desktop/dsh/harbor-ca.crt" -noout -subject -issuer -dates 2>&1 | head -5
echo "  是否 CA:"; openssl x509 -in "/mnt/c/Users/CC/Desktop/dsh/harbor-ca.crt" -noout -text 2>/dev/null | grep -A1 'Basic Constraints' | head -3

echo ""
echo "===== 2. Harbor 实际出示的证书链 ====="
echo | timeout 15 openssl s_client -connect harbor.wuxing.local:443 -servername harbor.wuxing.local 2>/dev/null | \
  openssl x509 -noout -subject -issuer -dates 2>&1 | head -5

echo ""
echo "===== 3. 用 CACert 校验（看是否真能验通）====="
echo | timeout 15 openssl s_client -connect harbor.wuxing.local:443 -servername harbor.wuxing.local \
  -CAfile "/mnt/c/Users/CC/Desktop/dsh/harbor-ca.crt" 2>&1 | grep -E 'Verify return code|verify error' | head -3

echo ""
echo "===== 4. 服务器是否发送完整链 ====="
echo | timeout 15 openssl s_client -connect harbor.wuxing.local:443 -servername harbor.wuxing.local -showcerts 2>/dev/null | grep -c 'BEGIN CERTIFICATE'
echo "  (1=只发叶子证书, 2+=发了链)"

echo ""
echo "===== 5. regctl registry set 的 tls 取值 ====="
regctl registry set --help 2>&1 | grep -i -A3 'tls'
