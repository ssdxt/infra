from server.db.models.department_model import DepartmentModel
from server.db.session import with_session
from server.knowledge_base.utils import KnowledgeFile
from typing import List, Dict
from datetime import datetime
from sqlalchemy import text

@with_session
def update_department_app_count(session) -> Dict:
    """
    更新单位应用数量
    """
    sql_update_app_count = '''
    UPDATE department 
    SET app_count = (
        SELECT COUNT(*) FROM app 
        WHERE app.dep_id = department.id
    )
    '''
    
    session.execute(text(sql_update_app_count))
    session.commit()
    
    return {"code": 0, "msg": "更新部门应用数量成功"}


@with_session
def department_add(session,
            name:str,
            desc:str,
            parent_id: int,
            theme_color: str = None,
            info: dict = None
                      ) -> Dict:
    
    user = session.query(DepartmentModel).filter_by(name=name).first()
    if user:
        return {"code":-1,"msg":"已经存在","data":{}}
    
    obj = DepartmentModel(name=name,desc=desc,parent_id=parent_id,app_type_ids=[1],theme_color=theme_color,info=info)
    session.add(obj)
    session.commit()
    #返回obj
    db_obj = session.query(DepartmentModel).filter_by(name=name).first()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def department_update(session,
                id:int,
                name:str= None,
                desc:str= None,
                parent_id:int= None,
                app_type_ids:List= None,
                theme_color:str = None,
                info:Dict= None
                      ) -> Dict:
    
    db_obj = session.query(DepartmentModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    if name and name != db_obj.name:
        _obj = session.query(DepartmentModel).filter_by(name=name).first()
        if _obj is not None:
            return {"code":-1,"msg":"该名字已经存在","data":{}}
        else:
            db_obj.name = name
    if desc is not None:
        db_obj.desc = desc  
    
    print(app_type_ids)
    if app_type_ids is not None:
        db_obj.app_type_ids = app_type_ids
        print(db_obj.app_type_ids)
        
        if app_type_ids and (2 in app_type_ids or 3 in app_type_ids):
            from server.db.models.app_model import AppModel
            from server.db.repository.app_repository import app_add
            
            existing_apps = session.query(AppModel).filter(
                AppModel.dep_id == id,
                AppModel.type_id.in_([2, 3])
            ).all()
            
            existing_type_ids = [app.type_id for app in existing_apps]
            
            if 2 in app_type_ids and 2 not in existing_type_ids:
                app_add(
                    type_id=2,
                    name="技术文档辅助生成",
                    kb_ids=[],
                    dep_id=id,
                    activate=True,
                    info={}
                )
            
            if 3 in app_type_ids and 3 not in existing_type_ids:
                app_add(
                    type_id=3,
                    name="个性化培训",
                    kb_ids=[],
                    dep_id=id,
                    activate=True,
                    info={"trainNum": 5, "greet": "您好，同学，今天也要好好学习啊。"}
                )
    
    if parent_id:
        db_obj.parent_id = parent_id
    if theme_color:
        db_obj.theme_color = theme_color
    if info:
        db_obj.info = info
    
    session.commit()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def department_delete(session,
                    id:int,
                    ) -> Dict:
    
    db_obj = session.query(DepartmentModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"该数据不存在","data":{}}
    session.delete(db_obj)
    session.commit()
    return {"code":0,"msg":"成功","data":{}}

@with_session
def department_list(session,id=None,name=None,page_start=None,page_end=None) -> Dict:

    update_department_app_count()
    db_objs = session.query(DepartmentModel)

    if id:
        db_objs = db_objs.filter_by(id=id)
    if name:
        db_objs = db_objs.filter(DepartmentModel.name.like('%' + name + '%'))

    db_objs = db_objs.order_by(DepartmentModel.id.desc())
    count = db_objs.count()

    if page_start is not None and page_end is not None:
        db_objs = db_objs.slice(page_start, page_end).all()
    else:
        db_objs = db_objs.all()

    data =[db_obj.to_out_dict() for db_obj in  db_objs]
    
    return {"code":0,"msg":"成功","data":{"count":count,"departments":data}}


@with_session
def department_detail(session,
                    id:int,
                    is_detail:bool=True
                    ) -> Dict:
    
    db_obj = session.query(DepartmentModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict(is_detail)}
