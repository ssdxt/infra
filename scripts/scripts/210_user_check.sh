#!/bin/bash
echo '== users 相关表 =='
docker exec cc-mysql mysql -uroot -p'Chicheng!234' omniknow -e 'SHOW TABLES LIKE "%user%";' 2>/dev/null
echo '== user 表账号列表 =='
for t in user users account; do
  docker exec cc-mysql mysql -uroot -p'Chicheng!234' omniknow -e "SELECT * FROM $t LIMIT 10;" 2>/dev/null && break
done
echo '== 密码哈希方案 =='
grep -rnE 'bcrypt|pbkdf2|passlib|hash_password|verify_password|sha256|argon' /ManualAI/OmniKnow/omniknow2/server --include='*.py' 2>/dev/null | grep -vE 'test|__pycache__' | head -10
