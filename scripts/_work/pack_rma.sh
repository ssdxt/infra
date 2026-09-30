#!/bin/bash
R=/deploy/rma-20260914-2106030737ZER3013372
sudo rm -rf $R
sudo mkdir -p $R/{npu-smi,ascend-plog,containers}

echo "########## 1. npu-smi 证据 ##########"
{
  echo "===== npu-smi info ====="; sudo npu-smi info 2>&1
  echo; echo "===== -t board ====="; sudo npu-smi info -t board -i 24 2>&1
  echo; echo "===== -t product ====="; sudo npu-smi info -t product -i 24 2>&1
  echo; echo "===== -t health chip0 ====="; sudo npu-smi info -t health -i 24 -c 0 2>&1
  echo; echo "===== -t health chip1 ====="; sudo npu-smi info -t health -i 24 -c 1 2>&1
  echo; echo "===== -t ecc chip0 ====="; sudo npu-smi info -t ecc -i 24 -c 0 2>&1
  echo; echo "===== -t ecc chip1 ====="; sudo npu-smi info -t ecc -i 24 -c 1 2>&1
  echo; echo "===== -t memory chip0 ====="; sudo npu-smi info -t memory -i 24 -c 0 2>&1
  echo; echo "===== -t memory chip1 ====="; sudo npu-smi info -t memory -i 24 -c 1 2>&1
  echo; echo "===== -t pcie-err chip0 ====="; sudo npu-smi info -t pcie-err -i 24 -c 0 2>&1
  echo; echo "===== -t temp chip0 ====="; sudo npu-smi info -t temp -i 24 -c 0 2>&1
  echo; echo "===== -t first-power-on-date ====="; sudo npu-smi info -t first-power-on-date -i 24 2>&1
} | sudo tee $R/npu-smi/npu-smi-all.txt >/dev/null

echo "########## 2. 系统环境 ##########"
{
  echo "===== OS ====="; grep -E "^(NAME|VERSION|PRETTY_NAME|VERSION_ID)=" /etc/os-release
  echo; echo "===== kernel ====="; uname -a
  echo; echo "===== driver version.info ====="; sudo cat /usr/local/Ascend/driver/version.info
  echo; echo "===== CANN version.cfg ====="; cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg
  echo; echo "===== CPU / MEM ====="; nproc; free -h
  echo; echo "===== PCIe 0b:00.0 ====="; sudo lspci -vv -s 0b:00.0 2>/dev/null | grep -iE "LnkCap|LnkSta|Region|Kernel driver"
  echo; echo "===== dmesg ascend ====="; sudo dmesg -T 2>/dev/null | grep -i ascend | tail -30
} | sudo tee $R/system-info.txt >/dev/null

echo "########## 3. 从 mis-tei 容器导出 ascend plog ##########"
C=bge-m3-npu
if sudo docker ps -a --format '{{.Names}}' | grep -qx "$C"; then
  sudo docker cp $C:/root/ascend/log $R/ascend-plog/ 2>&1 | head -2
  sudo docker logs $C > $R/containers/mis-tei-bge-m3-container.log 2>&1
  echo "  mis-tei 日志已导出"
else
  echo "  容器 $C 不在，跳过"
fi

echo
echo "########## 4. 从 MindIE 容器导出日志 ##########"
G=glm-4-9b-chat
if sudo docker ps -a --format '{{.Names}}' | grep -qx "$G"; then
  sudo docker cp $G:/usr/local/Ascend/mindie/1.0.0/mindie-service/logs $R/containers/mindie-logs 2>&1 | head -2
  sudo docker logs $G > $R/containers/mindie-container.log 2>&1
  sudo docker exec $G cat /usr/local/Ascend/mindie/1.0.0/mindie-llm/logs/pythonlog.log/* 2>/dev/null \
    > $R/containers/mindie-pythonlog.txt
  echo "  MindIE 日志已导出"
else
  echo "  容器 $G 不在，跳过"
fi

echo
echo "########## 5. 放入报修单文档 ##########"
sudo cp /tmp/rma-doc.md "$R/昇腾300I-Duo故障报修单.md" 2>/dev/null && echo "  已放入" || echo "  文档未上传，跳过"

echo
echo "########## 6. 打包 ##########"
sudo chmod -R a+r $R
cd /deploy || exit 1
sudo tar czf $R.tar.gz -C /deploy "$(basename $R)" 2>&1 | tail -2
sudo ls -la $R.tar.gz
echo
echo "########## 7. 内容清单 ##########"
sudo find $R -type f | sed "s|$R/||" | sort
echo
echo "总大小: $(sudo du -sh $R | awk '{print $1}')"
