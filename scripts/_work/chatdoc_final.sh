#!/bin/bash
echo "########## 1 宿主上 oceanbase 部署目录 ##########"
ls -la /deploy/infra/oceanbase/ 2>&1
echo "--- 递归前 40 项 ---"
find /deploy/infra/oceanbase -maxdepth 3 2>/dev/null | head -40

echo
echo "########## 2 oceanbase compose ##########"
for f in /deploy/infra/oceanbase/*.yml /deploy/infra/oceanbase/*.yaml; do
  [ -f "$f" ] && { echo "===== $f ====="; cat "$f"; }
done

echo
echo "########## 3 数据目录 / 配置目录有没有东西 ##########"
echo -n "  ob  大小: "; du -sh /deploy/infra/oceanbase/ob 2>&1
ls -la /deploy/infra/oceanbase/ob 2>&1
echo -n "  obd 大小: "; du -sh /deploy/infra/oceanbase/obd 2>&1
ls -la /deploy/infra/oceanbase/obd 2>&1
echo "--- obd 下 cluster/repository ---"
ls -la /deploy/infra/oceanbase/obd/cluster 2>&1
ls -la /deploy/infra/oceanbase/obd/repository 2>&1 | head

echo
echo "########## 4 全盘找 ob 的恢复包 ##########"
find / -maxdepth 6 -name "repository.tar.gz" 2>/dev/null | head -5
find / -maxdepth 6 -name "store.tar.gz" 2>/dev/null | head -5
find / -maxdepth 6 -name "etc.tar.gz" -path "*demo*" 2>/dev/null | head -5

echo
echo "########## 5 应用的数据库配置（哪个 IP/端口）##########"
echo "--- configs 目录 ---"
ls -la /deploy/code/chat_doc_0918/configs/ 2>&1
echo "--- 所有 DB URI ---"
grep -rn "SQLALCHEMY_DATABASE_URI" /deploy/code/chat_doc_0918/configs/ 2>/dev/null
grep -rn "mysql+pymysql\|mysql+pool" /deploy/code/chat_doc_0918/configs/ 2>/dev/null | head -10
echo "--- kb_config.py 的 DB 段 ---"
grep -n "SQLALCHEMY\|HOST\|PORT\|PASSWORD\|USERNAME\|DATABASE" /deploy/code/chat_doc_0918/configs/kb_config.py 2>/dev/null | head -20
echo "--- server_config.py 的 DB 段 ---"
grep -n "SQLALCHEMY\|HOST\|PORT\|PASSWORD\|USERNAME\|DATABASE\|2881" /deploy/code/chat_doc_0918/configs/server_config.py 2>/dev/null | head -20

echo
echo "########## 6 语音服务：模型路径与代码 ##########"
grep -n "AutoModel\|model=\|model_dir\|/deploy/models/speech" /deploy/code/melott/web_demo_seaco.py 2>/dev/null | head -20
echo "--- 模型目录是否存在 ---"
ls -la /deploy/models/speech/ 2>&1
ls -la /deploy/models/speech/iic/ 2>&1
echo "--- 目标模型目录内容 ---"
ls -la /deploy/models/speech/iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch/ 2>&1 | head -20

echo
echo "########## 7 API 服务实际能不能用（探活）##########"
curl -sk -m 10 -o /dev/null -w "  GET /            HTTP %{http_code}\n" https://127.0.0.1:8261/ 2>&1
curl -sk -m 10 -o /dev/null -w "  GET /docs        HTTP %{http_code}\n" https://127.0.0.1:8261/docs 2>&1
curl -s  -m 10 -o /dev/null -w "  GET 3333 (web)   HTTP %{http_code}\n" http://127.0.0.1:3333/ 2>&1
curl -sk -m 10 -o /dev/null -w "  GET 20400        HTTP %{http_code}\n" https://127.0.0.1:20400/ 2>&1
curl -sk -m 10 -o /dev/null -w "  GET 20401        HTTP %{http_code}\n" https://127.0.0.1:20401/ 2>&1

echo
echo "########## 8 应用日志里有没有数据库报错 ##########"
tail -120 /deploy/cc/logs/api_log.txt 2>&1 | grep -iE "error|refused|1045|2003|timeout|mysql|ocean|2881|exception" | tail -25
echo "--- logs 目录 ---"
ls -lat /deploy/cc/logs/ 2>&1 | head -10
