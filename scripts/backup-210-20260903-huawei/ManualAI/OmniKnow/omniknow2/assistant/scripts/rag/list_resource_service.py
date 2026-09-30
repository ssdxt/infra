from fastapi import FastAPI, HTTPException
import json
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# ==== MySQL 配置 ====
config = {
    "host": "127.0.0.1",
    "port": 19806,
    "user": "root",
    "password": "cc123456",
    "database": "omniknow",
}

# 创建 SQLAlchemy Engine（内部自带连接池）
def get_engine() -> Engine:
    user = config["user"]
    password = config["password"]
    host = config["host"]
    port = config["port"]
    database = config["database"]

    # 注意：如果密码里有特殊字符，建议用 urllib.parse.quote_plus 编码
    db_url = (
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
        "?charset=utf8mb4"
    )
    engine = create_engine(
        db_url,
        pool_pre_ping=True,  # 自动检测失效连接
    )
    return engine

engine = get_engine()

app = FastAPI()


@app.get("/knowledge/list_resources")
def list_resources():
    """
    返回 omniknow 数据库中 knowledgebase_detail 表的所有数据。
    用 pandas 读取成 DataFrame，然后转 JSON 返回。
    """
    try:
        query = "SELECT * FROM knowledgebase_detail"
        df = pd.read_sql(query, engine)
        # DataFrame to json
        data = df.to_dict(orient="records")
        return data
    except Exception as e:
        # 出错时返回 500
        raise HTTPException(status_code=500, detail=f"Database query error: {e}")
