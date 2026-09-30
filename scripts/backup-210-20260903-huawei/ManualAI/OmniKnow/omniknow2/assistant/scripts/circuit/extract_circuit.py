import pandas as pd
import json
def load_jsonl(path: str):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON decode error in line {i}: {e}\nLine content: {line}")
    return records
detail_jsons = load_jsonl("/mnt/ddata2/user/zhangga/omniknow2/assistant/scripts/circuit/data.jsonl")
detail_map = {
    d["connectorID"]: d
    for d in detail_jsons
    if "connectorID" in d
}

sop = "SOP8"
oss_template = "http://183.129.232.94:18372/public/Tesla/{sop}/Interactive%20Schematics/{filename}.svg"
records = pd.read_csv("/mnt/ddata2/user/zhangga/omniknow2/assistant/scripts/circuit/item_to_page.csv")

records[['connectorID', 'cavityID']] = records['pid_number'].str.split('-', n=1, expand=True)
records['SOP'] = sop
records.rename(columns={'pid_number':"pin_number","pid_number_id":"pin_number_id"},inplace=True)

records = records[records['page_number'] >=2] # 过滤前两页
records['url'] = [oss_template.format(sop=sop,filename=r["page_name"].replace(" ","_").lower()) for r in records.to_records()]

records["details"] = records["connectorID"].map(detail_map)

records.to_json("/mnt/ddata2/user/zhangga/omniknow2/assistant/scripts/item_to_page.json",indent=4,orient="records", force_ascii=False)