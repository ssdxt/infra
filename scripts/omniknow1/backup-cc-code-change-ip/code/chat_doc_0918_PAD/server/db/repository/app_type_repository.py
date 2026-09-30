from server.db.models.app_type_model import AppTypeModel
from server.db.session import with_session
from server.knowledge_base.utils import KnowledgeFile
from typing import List, Dict

from datetime import datetime


@with_session
def app_type_add(session,
            name:str,
            desc:str,
            f_config: Dict = {},
            b_config: Dict = {},
                      ) -> Dict:
    
    db_obj = session.query(AppTypeModel).filter_by(name=name).first()
    if db_obj:
        return {"code":-1,"msg":"应用类型已经存在"}
    
    obj = AppTypeModel(name=name,desc=desc,f_config=f_config,b_config=b_config)
    session.add(obj)
    session.commit()
    #返回obj
    db_obj = session.query(AppTypeModel).filter_by(name=name).first()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def app_type_update(session,
                id:int,
                desc:str,
                f_config:Dict,
                b_config:Dict,
                      ) -> Dict:
    
    db_obj = session.query(AppTypeModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"应用类型不存在"}
    if desc:
        db_obj.desc = desc
    if f_config:
        db_obj.f_config = f_config
    if b_config:
        db_obj.b_config = b_config
    
    session.commit()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def app_type_delete(session,
                    id:int,
                    ) -> Dict:
    
    db_obj = session.query(AppTypeModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"该数据不存在"}
    session.delete(db_obj)
    session.commit()
    return {"code":0,"msg":"成功","data":{}}

@with_session
def app_type_list(session,app_type_ids=None) -> Dict:
    
    db_objs = session.query(AppTypeModel)

    if app_type_ids:
        db_objs = db_objs.filter(AppTypeModel.id.in_(app_type_ids))

    db_objs = db_objs.order_by(AppTypeModel.id.desc())
    db_objs = db_objs.all()
    
    count=len(db_objs)
    data =[db_obj.to_out_dict() for db_obj in  db_objs]
    
    return {"code":0,"msg":"成功","data":{"count":count,"app_types":data}}


@with_session
def app_type_detail(session,
                    id:int,
                    ) -> Dict:
    
    db_obj = session.query(AppTypeModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def _app_type_name_list(session,
                    ids:list,
                    ) -> Dict:
    db_obj = session.query(AppTypeModel.id,AppTypeModel.name).filter(AppTypeModel.id.in_(ids)).all()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":[]}
    data = []
    for row in db_obj:
        data.append({"id":row.id,"name":row.name})
    return {"code":0,"msg":"成功","data":data}
