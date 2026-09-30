#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成特斯拉维保委托单模拟数据（杭州服务中心/服务点）
输出：CSV / JSONL（二选一或都输出）

表头（包含你两段表头的并集，避免缺列）：
委托书号, 维保门店, 车型, 行驶里程, 客户姓名, 服务顾问, 技师, 保养/维修, 维保项目, 记录, 费用合计, 进站时间, 出站时间
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import math  # For lognormal, etc.
import numpy as np  # Assuming numpy is available for better distributions
import pandas as pd
from sqlalchemy import create_engine


# -----------------------------
# 基础数据
# -----------------------------
STORES: List[str] = [
    "沈半特斯拉中心（拱墅区沈半路）",
    "杭州萧山特斯拉中心（萧山区）",
    "杭州西溪特斯拉中心（西溪湿地周边）",
    "杭州临平特斯拉中心（临平区域）",
    "杭州未来科技城特斯拉中心（余杭/未来科技城）",
    "杭州金沙湖特斯拉中心（钱江新城/金沙湖）",
    "龙湖滨江天街特斯拉城市展厅/服务点",
    "西溪天街特斯拉城市展厅/服务点",
    "万象城特斯拉城市展厅/服务点",
    "大悦城特斯拉城市展厅/服务点",
    "萧山直营钣喷中心（车身修复）",
]

# 门店权重：假设核心门店更忙碌，使用 Pareto-like 分布（肥尾：少数门店处理多数订单）
STORE_WEIGHTS: List[int] = [int(100 / (i+1)**1.5) for i in range(len(STORES))]  # 肥尾权重，头部门店更高

# 车型分布：Model 3 50%、Model Y 40%、Model X 7%、Model S 3% (已有权重，保持)
MODEL_WEIGHTS: List[Tuple[str, int]] = [
    ("Model 3", 50),
    ("Model Y", 40),
    ("Model X", 7),
    ("Model S", 3),
]

# 维保项目：小保养/大保养/洗车 + 随机维修项目（特斯拉主要部件）
MAINTENANCE_ITEMS = ["小保养", "大保养", "洗车"]

REPAIR_ITEMS = [
    "高压电池包检测/维修",
    "驱动电机检测/维修",
    "逆变器/功率模块检测",
    "充电口/充电控制模块维修",
    "12V 低压系统/电瓶更换",
    "制动系统检修（刹车片/刹车盘）",
    "悬架系统检修（摆臂/减震）",
    "转向系统检修",
    "轮胎更换/动平衡",
    "空调系统检修（压缩机/冷媒）",
    "车机中控屏/娱乐系统检修",
    "摄像头/视觉系统校准",
    "雷达/传感器校准",
    "车门把手/门锁机构维修",
    "玻璃更换（前挡/侧窗）",
    "雨刮系统检修",
    "钣金喷漆修复",
    "底盘异响排查",
]

# 维修项目权重：常见项目更高频（如轮胎、刹车），稀有项目低频（肥尾）
REPAIR_WEIGHTS: List[int] = [int(50 / (i+1)**1.2) for i in range(len(REPAIR_ITEMS))]

# 费用：固定 + 区间随机（改为 lognormal 分布以模拟肥尾：大多数低成本，少数高成本）
FEE_MAP: Dict[str, Tuple[int, int]] = {
    "小保养": (500, 500),
    "大保养": (2000, 2000),
    "洗车": (50, 50),

    # 维修项（区间，用于 clip）
    "高压电池包检测/维修": (1500, 12000),
    "驱动电机检测/维修": (1200, 8000),
    "逆变器/功率模块检测": (800, 6000),
    "充电口/充电控制模块维修": (300, 2500),
    "12V 低压系统/电瓶更换": (400, 1800),
    "制动系统检修（刹车片/刹车盘）": (600, 3500),
    "悬架系统检修（摆臂/减震）": (800, 6000),
    "转向系统检修": (600, 4000),
    "轮胎更换/动平衡": (800, 6000),
    "空调系统检修（压缩机/冷媒）": (300, 5000),
    "车机中控屏/娱乐系统检修": (500, 7000),
    "摄像头/视觉系统校准": (300, 1500),
    "雷达/传感器校准": (300, 2000),
    "车门把手/门锁机构维修": (300, 2500),
    "玻璃更换（前挡/侧窗）": (800, 6000),
    "雨刮系统检修": (100, 800),
    "钣金喷漆修复": (800, 12000),
    "底盘异响排查": (200, 1200),
}

# 中文姓名生成（简单版）
SURNAMES = list("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦许何吕施张孔曹严华金魏陶姜谢邹喻柏章")
GIVEN_CHARS = list("一乙二十丁厂七卜人入八九几儿了乃刀力又三干于亏士工土才下寸大丈与万上小口巾山千乞川亿个勺久凡及夕丸么广亡门义之尸已弓己卫子也女飞刃习叉马乡丰王井开夫天无元专云扎艺木五支厅不太犬区历尤友匹车巨牙屯比互切瓦止少日中贝冈内水见午牛手毛气升长仁什片仆化仇币仍仅斤爪反介父从今凶分乏公仓月氏勿欠风丹匀乌凤勾文六方火为斗忆订计户认心尺引丑巴孔队办以允予劝双书幻玉刊末未示击打巧正扑扒功扔去甘世古节本术可丙左厉石右布龙平灭轧东卡北占业旧帅归旦目叶甲申叮电号田由史只央兄叼叫另叨叹四生失禾丘付仗代仙们仪白仔他斥瓜乎丛令用甩印乐句匆册犯外处冬鸟务包饥主市立闪兰半汁汇头汉宁它讨写让礼训议讯记永司尼民出辽奶奴加召皮边发孕圣对台矛纠母幼丝式刑动扛寺吉扣考托老巩圾执扩扫地扬场耳共芒亚芝朽朴机权过臣吏再协西压厌在有百存而页匠夸夺灰达列死成夹轨邪尧划迈毕至此贞师尘尖劣光当早吐吓虫曲团同吊吃因吸吗屿岁帆回岂刚则肉网年朱先丢廷舌竹迁乔伟传乒乓休伍伏优伐延件任伤价伦佑体何作你伯低住位伴身皂佛近彻役返余希坐谷妥含邻岔肝肚肠龟免狂犹角删条卵岛迎饭饮系言")

def random_cn_name() -> str:
    surname = random.choice(SURNAMES)
    # 名字 1~2 字
    given_len = 1 if random.random() < 0.35 else 2
    given = "".join(random.choice(GIVEN_CHARS) for _ in range(given_len))
    return f"{surname}{given}"

def desensitized_hash_name(name: str, salt: str = "tesla_demo_salt") -> str:
    h = hashlib.sha256((salt + name).encode("utf-8")).hexdigest().upper()
    return f"{name[:1]}**#{h[:8]}"

def weighted_choice(pairs: List[Tuple[str, int]]) -> str:
    items, weights = zip(*pairs)
    return random.choices(items, weights=weights, k=1)[0]

def random_mileage() -> int:
    # 正态分布：平均 50,000 km，标准差 20,000 km，clip 到 10,000 ~ 150,000
    mu, sigma = 50000, 20000
    mileage = int(np.random.normal(mu, sigma))
    return max(10000, min(150000, mileage))

def random_store() -> str:
    # 加权选择门店
    return random.choices(STORES, weights=STORE_WEIGHTS, k=1)[0]

def build_advisors(n: int = 50) -> list[str]:
    raw = [random_cn_name() for _ in range(n)]
    return [desensitized_hash_name(x, salt="advisor") for x in raw]

def build_techs(n: int = 200) -> list[str]:
    raw = [random_cn_name() for _ in range(n)]
    return [desensitized_hash_name(x, salt="tech") for x in raw]

# 为顾问/技师添加权重：肥尾分布，少数精英处理多数订单
def weighted_random_choice(items: List[str]) -> str:
    weights = [int(100 / (i+1)**1.5) for i in range(len(items))]  # Pareto-like
    return random.choices(items, weights=weights, k=1)[0]

def random_in_datetime(start_year=2020, end_year=2025) -> datetime:
    """
    修改为非均匀：订单量随年份增长（指数增长模拟销量增加），肥尾向近期
    年份权重：2020:1, 2021:2, 2022:4, 2023:8, 2024:16, 2025:32
    """
    years = list(range(start_year, end_year + 1))
    year_weights = [2 ** (y - start_year) for y in years]
    year = random.choices(years, weights=year_weights, k=1)[0]

    # 月/日 均匀，但可进一步调整为季节性（e.g., 夏季多空调维修，但暂不加）
    month = random.randint(1, 12)
    day = random.randint(1, 28)  # 简化
    hour = random.randint(7, 17)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)

    try:
        dt = datetime(year, month, day, hour, minute, second)
    except ValueError:
        dt = datetime(year, month, 28, hour, minute, second)  # 安全
    return dt

def random_out_datetime(in_dt: datetime) -> datetime:
    """
    出站时间：当天/次日/2日后，使用指数分布偏移（大多数当天，少数延后）
    小时加：Exponential分布，scale=3 (平均3小时)，clip
    """
    day_offset = random.choices([0, 1, 2, 3], weights=[70, 20, 8, 2], k=1)[0]  # 肥尾延后
    hour_add = int(np.random.exponential(scale=3))  # 平均3小时
    hour_add = max(1, min(8 + day_offset * 24, hour_add))  # clip
    minute_add = random.randint(0, 59)
    out_dt = in_dt + timedelta(days=day_offset, hours=hour_add, minutes=minute_add)
    return out_dt

def pick_service_item() -> str:
    # 保养类型权重：小保养多，大保养少，洗车少
    # 小保养 40%, 大保养 15%, 洗车 10%, 维修 35%
    r = random.random()
    if r < 0.40:
        return "小保养"
    if r < 0.55:
        return "大保养"
    if r < 0.65:
        return "洗车"
    # 维修：加权选择
    return random.choices(REPAIR_ITEMS, weights=REPAIR_WEIGHTS, k=1)[0]

def service_type(item: str) -> str:
    if item in ("小保养", "大保养", "洗车"):
        return "保养"
    return "维修"

def calc_fee(item: str) -> int:
    low, high = FEE_MAP.get(item, (300, 5000))
    if low == high:
        return low
    # Lognormal 分布模拟肥尾：大多数接近 low，少数高至 high
    mu = math.log((low + high) / 2)  # 粗略中位
    sigma = 0.5  # 调整 variance 以控制尾巴
    fee = int(np.random.lognormal(mu, sigma))
    return max(low, min(high, fee))

def build_record(item: str) -> str:
    templates = [
        f"{item}：已完成常规检查与测试，车辆状态正常。",
        f"{item}：发现轻微异常，已处理并复测通过。",
        f"{item}：建议后续复查相关部件，已告知客户。",
        f"{item}：完成工单闭环，客户确认无异议。",
    ]
    return random.choice(templates)

def gen_rows(n: int, seed: int | None = None) -> List[Dict[str, object]]:
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    advisors = build_advisors(50)
    techs = build_techs(200)

    rows: List[Dict[str, object]] = []
    for _ in range(n):
        order_id = str(uuid.uuid4())
        store = random_store()
        model = weighted_choice(MODEL_WEIGHTS)
        mileage = random_mileage()

        raw_name = random_cn_name()
        customer = desensitized_hash_name(raw_name, salt="customer")

        advisor = weighted_random_choice(advisors)
        tech = weighted_random_choice(techs)

        item = pick_service_item()
        svc_type = service_type(item)

        fee = calc_fee(item)
        in_dt = random_in_datetime(2020, 2025)
        out_dt = random_out_datetime(in_dt)

        row = {
            "委托书号": order_id,
            "维保门店": store,
            "车型": model,
            "行驶里程": mileage,
            "客户姓名": customer,
            "服务顾问": advisor,
            "技师": tech,
            "保养/维修": svc_type,
            "维保项目": item,
            "记录": build_record(item),
            "费用合计": fee,
            "进站时间": in_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "出站时间": out_dt.strftime("%Y-%m-%d %H:%M:%S"),
        }
        rows.append(row)
    rows.sort(
        key=lambda r: datetime.strptime(r["进站时间"], "%Y-%m-%d %H:%M:%S"),
        reverse=True,
    )

    return rows

def write_csv(rows: List[Dict[str, object]], path: str) -> None:
    if not rows:
        raise ValueError("rows is empty")

    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

def write_jsonl(rows: List[Dict[str, object]], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")



insert_db = True
num = 200000
seed = 12
path = "tesla_service_orders_20260103.csv"
rows = gen_rows(num, seed=seed)

write_csv(rows, path)
print(f"[OK] CSV written: {path} ({len(rows)} rows)")

if insert_db:
    engine = create_engine("mysql+pymysql://root:cc123456@127.0.0.1:19806/tesla_service?charset=utf8mb4")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.to_sql("门店车辆维修保养记录", con=engine, if_exists="append", index=False, chunksize=2000, method="multi")
    print("done", len(df))