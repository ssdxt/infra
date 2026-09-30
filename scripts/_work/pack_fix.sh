#!/bin/bash
R=/deploy/rma-20260914-2106030737ZER3013372

echo "########## 补导容器日志（用 sudo sh -c 让重定向也以 root 执行）##########"

C=bge-m3-npu
if sudo docker ps -a --format '{{.Names}}' | grep -qx "$C"; then
  sudo sh -c "docker logs $C > $R/containers/mis-tei-bge-m3-container.log 2>&1"
  echo "  mis-tei 容器日志: $(sudo wc -l < $R/containers/mis-tei-bge-m3-container.log) 行"
fi

G=glm-4-9b-chat
if sudo docker ps -a --format '{{.Names}}' | grep -qx "$G"; then
  sudo sh -c "docker logs $G > $R/containers/mindie-container.log 2>&1"
  echo "  MindIE 容器日志: $(sudo wc -l < $R/containers/mindie-container.log) 行"
  sudo sh -c "docker cp $G:/usr/local/Ascend/mindie/1.0.0/mindie-service/logs/. $R/containers/mindie-logs/ 2>/dev/null" || true
  sudo sh -c "cat /dev/null > $R/containers/mindie-pythonlog.txt"
  for f in $(sudo find $R/containers/mindie-logs -name "*.log" 2>/dev/null); do
    sudo sh -c "cat '$f' >> $R/containers/mindie-pythonlog.txt"
  done
fi

echo
echo "########## 重新打包 ##########"
sudo rm -f $R.tar.gz
sudo chmod -R a+r $R
cd /deploy || exit 1
sudo tar czf $R.tar.gz -C /deploy "$(basename $R)"
sudo chmod 644 $R.tar.gz
sudo ls -la $R.tar.gz

echo
echo "########## 最终清单 ##########"
sudo find $R -type f -printf "%10s  %p\n" | sed "s|$R/||" | sort -k2
echo
echo "总大小: $(sudo du -sh $R | awk '{print $1}')"
