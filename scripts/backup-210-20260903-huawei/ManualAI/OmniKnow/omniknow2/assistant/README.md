docker-compose -f docker-compose.yaml up -d
docker-compose -f docker-compose.yaml down

# 部署流程
## 环境配置
conda create -n agenticflow python=3.12
pip install -r assistant/requirements.txt


# 启动脚本 默认 8366 接口
conda activate agenticflow

source assistant/.venv/bin/activate

nohup python assistant/server.py > assistant/log/server_$(date +%F_%H-%M-%S).log 2>&1 &