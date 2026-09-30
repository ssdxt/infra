import pandas as pd
from sqlalchemy import create_engine

# csv_path = "/mnt/ddata2/user/zhangga/omniknow2/tesla_service_orders.csv"
csv_path = "/mnt/ddata2/user/zhangga/omniknow2/assistant/scripts/tabular/tesla_repair_code.csv"
# 你的 CSV 是 utf-8-sig，就用 utf-8-sig 读
df = pd.read_csv(csv_path, encoding="utf-8-sig")
df = df.rename(columns={
    "id": "id",
    "code": "校正代码",
    "name": "中文含义",
    "workType": "施工类型",
    "modelID": "车型代码",
    "modelName": "车型名称",
    "frt": "平均维修工时",
    "chargedHours": "耗时",
    "procedureURL": "相关链接",
})

engine = create_engine("mysql+pymysql://root:cc123456@127.0.0.1:19806/tesla_service?charset=utf8mb4")
df.drop_duplicates(subset=['id','车型代码'],inplace=True)
df.to_sql("车辆校正代码与含义", con=engine, if_exists="append", index=False, chunksize=2000, method="multi")
print("done", len(df))
