#!/bin/bash
set +e
IMG=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/quay.io/oceanbase/oceanbase-ce:4.3.3.0-100000142024101215-linuxarm64
OBD=/deploy/infra/oceanbase/obd

echo "=========== 0 现状 ==========="
echo -n "  repository.tar.gz: "; ls -la $OBD/repository.tar.gz 2>&1 | tail -1
echo -n "  repository/oceanbase-ce: "; ls -la $OBD/repository/oceanbase-ce/ 2>&1 | tail -1
echo "  磁盘:"; df -h / | tail -1

echo
echo "=========== 1 从镜像提取 repository.tar.gz 到宿主 ==========="
docker rm -f obtmp 2>/dev/null >/dev/null
docker create --name obtmp --entrypoint /bin/true "$IMG" >/dev/null 2>&1
docker cp obtmp:/root/.obd/repository.tar.gz "$OBD/repository.tar.gz" 2>&1
docker rm -f obtmp >/dev/null 2>&1
ls -la "$OBD/repository.tar.gz" 2>&1

echo
echo "=========== 2 重建 oceanbase 容器 ==========="
docker rm -f oceanbase-ce 2>&1
bash /deploy/infra/oceanbase/docker-run.sh 2>&1
sleep 12
docker ps --filter name=oceanbase-ce --format '  {{.Names}} | {{.Status}}'

echo
echo "=========== 3 等 observer（最多 10 分钟）==========="
READY=0
for i in $(seq 1 40); do
  sleep 15
  if docker exec oceanbase-ce ss -lnt 2>/dev/null | grep -q ':2881'; then
    echo "  [第 ${i} 轮 / 约 $((i*15)) 秒] 2881 已监听"
    READY=1
    break
  fi
  echo "  [第 ${i} 轮 / 约 $((i*15)) 秒] 还没起来"
done

echo
echo "=========== 4 容器日志尾部 ==========="
docker logs --tail 60 oceanbase-ce 2>&1 | tail -60

echo
echo "=========== 5 内部状态 ==========="
echo "--- 进程 ---"
docker exec oceanbase-ce sh -c 'ps -ef | head -15' 2>&1
echo "--- /root/ob ---"
docker exec oceanbase-ce sh -c 'ls -la /root/ob 2>&1 | head -12' 2>&1
echo "--- .obd/repository ---"
docker exec oceanbase-ce sh -c 'ls -la /root/.obd/repository/oceanbase-ce/ 2>&1' 2>&1
echo "--- 监听 ---"
docker exec oceanbase-ce ss -lnt 2>&1 | head -12

echo
echo "=========== 6 数据库登录测试 ==========="
docker exec oceanbase-ce obclient -h127.1 -P2881 -uroot@test -p12345 -e "show databases;" 2>&1 | head -20

echo
echo "=========== 7 宿主连 2881 ==========="
timeout 6 bash -c 'cat < /dev/null > /dev/tcp/127.0.0.1/2881' 2>/dev/null && echo "  127.0.0.1:2881 通" || echo "  127.0.0.1:2881 不通"
/root/anaconda3/envs/recovery/bin/python -c "import pymysql;c=pymysql.connect(host='127.0.0.1',port=2881,user='root@test',password='12345',connect_timeout=8);cur=c.cursor();cur.execute('show databases');print('  pymysql OK ->',[r[0] for r in cur.fetchall()])" 2>&1 | tail -3

echo
echo "READY=$READY"
