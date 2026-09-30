# from server.db.models.user_info_model import UserInfoModel
from server.db.models.app_model import AppModel
from server.db.models.app_type_model import AppTypeModel
from server.db.models.department_model import DepartmentModel
from server.db.session import with_session
from server.knowledge_base.utils import KnowledgeFile
from typing import List, Dict

from datetime import datetime, timezone, timedelta

def beijing_time():
    """
    返回当前北京时间
    """
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)


@with_session
def app_add(session,
            type_id:int,
            name:str,
            kb_ids:List,
            dep_id:int,
            desc:str=None,
            # create_time:str,           
            assistant_type:str=None,
            hi:str=None,
            questions:List=None,          
            digital_human:str=None,
            digital_human_voice:str=None,
            # update_time:str,
            llm_model:str=None,
            url:str=None,
            activate:bool=True,
            info: Dict = {},
            user_email:str=None
                      ) -> Dict:
    
    user = session.query(AppModel).filter_by(dep_id=dep_id,name=name).first()
    if user:
        return {"code":-1,"msg":"已经存在","data":{}}
    
    obj = AppModel(type_id=type_id,name=name,desc=desc,kb_ids=kb_ids,assistant_type=assistant_type,hi=hi,questions=questions,dep_id=dep_id,digital_human=digital_human,llm_model=llm_model,url=url,activate=activate,info = info)
    session.add(obj)
    session.commit()
    #返回obj
    db_obj = session.query(AppModel).filter_by(dep_id=dep_id,name=name).first()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def app_update(session,
                id:int,
                name:str=None,
                desc:str=None,
                # create_time:str,
                kb_ids:List=None,
                assistant_type:str=None,
                hi:str=None,
                questions:List=None,
                dep_id:int=None,
                digital_human:str=None,
                digital_human_voice:str=None,
                # update_time:str,
                llm_model:str=None,
                url:str=None,
                activate:bool=None,
                info: Dict = {},
                user_email:str=None
                      ) -> Dict:
    
    db_obj = session.query(AppModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    
    if name:
        db_obj.name = name
    if desc:
        db_obj.desc = desc
    if kb_ids:
        db_obj.kb_ids = kb_ids
    if assistant_type:
        db_obj.assistant_type = assistant_type 
    if hi:
        db_obj.hi = hi
    if questions is not None:
        db_obj.questions = questions
    if dep_id:
        db_obj.dep_id = dep_id
    if digital_human:
        db_obj.digital_human = digital_human
    if llm_model:
        db_obj.llm_model = llm_model
    if url:
        db_obj.url = url
    if info:
        db_obj.info = info
        
    if activate is not None:
        db_obj.activate = activate
    db_obj.update_time = beijing_time()
    session.commit()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def app_delete(session,
                    id:int,
                    ) -> Dict:
    
    db_obj = session.query(AppModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"该权限不存在","data":{}}
    session.delete(db_obj)
    session.commit()
    return {"code":0,"msg":"成功","data":{}}

@with_session
def app_list(session,dep_id,name:str=None,assistant=True,page_start=None, page_end=None) -> Dict:
    
    db_objs = session.query(AppModel)
    if assistant is True:
        db_objs = db_objs.filter(AppModel.type_id == 1)
    db_objs = db_objs.order_by(AppModel.id.desc())
    
    if dep_id:
        db_objs = db_objs.filter_by(dep_id=dep_id)
    if name:
        db_objs = db_objs.filter(AppModel.name.like('%' + name + '%'))
    
    count = db_objs.count()

    if page_start is not None and page_end is not None:
        db_objs = db_objs.slice(page_start,page_end).all()
    else:
        db_objs = db_objs.all()
    
    data =[db_obj.to_out_dict() for db_obj in  db_objs]
    
    return {"code":0,"msg":"成功","data":{"count":count,"apps":data}}

@with_session
def specific_app_list(session,dep_id) -> Dict:
    
    db_objs = session.query(AppModel)
    db_objs = db_objs.filter(AppModel.type_id != 1)
    db_objs = db_objs.order_by(AppModel.id.desc())
    
    if dep_id:
        db_objs = db_objs.filter_by(dep_id=dep_id)
    
    count = db_objs.count()
    db_objs = db_objs.all()
    
    data =[db_obj.to_out_dict() for db_obj in  db_objs]
    
    return {"code":0,"msg":"成功","data":{"count":count,"apps":data}}

import copy

@with_session
def app_token_save(session,id:int,access_token:str,user_email:str) -> Dict:
    
    db_obj = session.query(AppModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"该应用不存在","data":{}}
    
    current_info = copy.deepcopy(db_obj.info)
    current_info["access_token"] = access_token
    current_info["update_user_email"] = user_email
    db_obj.info = current_info
    db_obj.update_time = beijing_time()

    session.commit()
    return {"code":0,"msg":"成功","data":db_obj.info}

@with_session
def app_detail(session,
                    id:int,
                    role:int=None,
                    is_detail:bool=True
                    ) -> Dict:
    
    db_obj = session.query(AppModel).filter_by(id=id).first()
    # db_obj = session.query(AppModel,AppTypeModel.name,DepartmentModel.name).outerjoin(AppTypeModel,AppModel.type_id==AppTypeModel.id).outerjoin(DepartmentModel,AppModel.dep_id==DepartmentModel.id).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    if db_obj.activate is False and role >= 3:
        return {"code":-1,"msg":"该应用已停用,请联系管理员激活","data":{}}
    
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict(is_detail)}



 # print("db_obj:",db_obj)
    # db_dict = {
    #     "id" : db_obj[0].id,
    #     "type_id" : db_obj[0].type_id,
    #     "name": db_obj[0].name,
    #     "desc" : db_obj[0].desc,
    #     "create_time": db_obj[0].create_time.strftime("%Y-%m-%d %H:%M:%S") if db_obj[0].create_time else "",
    #     "kb_ids": db_obj[0].kb_ids,
    #     "hi" : db_obj[0].hi,
    #     "questions" : db_obj[0].questions,
    #     "dep_id" : db_obj[0].dep_id,
    #     "update_time" : db_obj[0].update_time.strftime("%Y-%m-%d %H:%M:%S") if db_obj[0].update_time else "",
    #     "llm_model" : db_obj[0].llm_model,
    #     "url" : db_obj[0].url,
    #     "activate" : db_obj[0].activate,
    #     "type_name":db_obj[1],
    #     "dep_name":db_obj[2]
    # }
    # print("db_obj:",db_dict)
    # return {"code":0,"msg":"成功","data":db_dict}


# @with_session
# def _app_name_list(session,
#                     ids:list,
#                     ) -> Dict:
#     db_obj = session.query(AppModel.id,AppModel.name,AppModel.type_id,AppModel.desc).filter(AppModel.id.in_(ids)).all()
#     if db_obj is None:
#         return {"code":-1,"msg":"数据不存在","data":[]}
#     data = []
#     for row in db_obj:
#         data.append({"id":row.id,"name":row.name,"type_id":row.type_id,"desc":row.desc})
#     return {"code":0,"msg":"成功","data":data}
   
@with_session
def _app_name_list(session, ids: list) -> Dict:
    db_obj = session.query(AppModel.id, AppModel.name, AppModel.type_id, AppModel.desc, AppModel.info).filter(AppModel.id.in_(ids)).all()  
    if db_obj is None:
        return {"code": -1, "msg": "数据不存在", "data": []}
    data = []
    for row in db_obj:
        logo_url = row.info.get("app_logo", "") if row.info else ""
        type_name = ""
        if row.type_id:
            from server.db.repository.app_type_repository import app_type_detail
            app_type = app_type_detail(id=row.type_id)
            if app_type and app_type.get("data"):
                type_name = app_type["data"].get("name", "")
        data.append({
            "id": row.id,
            "name": row.name,
            "type_id": row.type_id,
            "type_name": type_name,
            "desc": row.desc,
            "logo_url": logo_url
        })
    
    return {"code": 0, "msg": "成功", "data": data}

@with_session
def app_logo_update(session, id:int, app_logo:str) -> Dict:
    
    db_obj = session.query(AppModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code": -1, "msg": "应用不存在", "data": {}}

    current_info = copy.deepcopy(db_obj.info) if db_obj.info else {}
    
    current_info["app_logo"] = app_logo
    
    db_obj.info = current_info
    
    session.commit()
    
    return {"code": 0, "msg": "应用logo上传成功", "data": {}}

@with_session
def app_job_update(session,id:int,job_titles:list) -> Dict:
    
    db_obj = session.query(AppModel).filter_by(id=id).first()
    if db_obj is None:
        return []

    old_job_titles = db_obj.job_titles if db_obj.job_titles else []

    if job_titles is not None:
        db_obj.job_titles = job_titles

    session.commit()
    
    return old_job_titles