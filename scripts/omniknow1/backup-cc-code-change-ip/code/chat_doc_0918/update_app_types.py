import sys
sys.path.append("./")

from server.db.base import SessionLocal
from server.db.models.app_type_model import AppTypeModel
from datetime import datetime, timezone, timedelta


def bulk_update_app_names_by_type_id():
    session = SessionLocal()
    try:
        objs1 = session.query(AppTypeModel).filter_by(id=1).all()
        for o in objs1:
            o.name = "智能维修助手"
        objs2 = session.query(AppTypeModel).filter_by(id=2).all()
        for o in objs2:
            o.name = "技术文档辅助生成"
        objs3 = session.query(AppTypeModel).filter_by(id=3).all()
        for o in objs3:
            o.name = "个性化培训"
        session.commit()
        return {"code":0,"msg":"成功","data":{"updated_type_1":len(objs1),"updated_type_2":len(objs2),"updated_type_3":len(objs3)}}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def main():
    result = bulk_update_app_names_by_type_id()
    import json
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
