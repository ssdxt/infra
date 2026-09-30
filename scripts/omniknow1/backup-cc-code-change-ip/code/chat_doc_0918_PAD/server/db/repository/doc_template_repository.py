from server.db.models.user_info_model import UserInfoModel
from server.db.models.doc_template_model import DocTemplateModel
from server.db.session import with_session
from server.knowledge_base.utils import KnowledgeFile
from typing import List, Dict
from sqlalchemy import text, func

@with_session
def update_doc_template_counts(session, dep_id=None) -> Dict:
    """
    更新文档模板的使用计数
    """
    from server.db.models.doc_history_model import DocHistoryModel
    
    template_query = session.query(DocTemplateModel.id)
    if dep_id is not None:
        template_query = template_query.filter_by(dep_id=dep_id)
    
    template_ids = [item[0] for item in template_query.all()]
    
    if not template_ids:
        return {"code": 0, "msg": "没有找到需要更新的模板"}

    count_query = session.query(
        DocHistoryModel.doc_template_id,
        func.count(DocHistoryModel.id).label('usage_count')
    ).filter(
        DocHistoryModel.doc_template_id.in_(template_ids)
    ).group_by(
        DocHistoryModel.doc_template_id
    )
    
    update_count = 0
    for row in count_query:
        template_id = row[0]
        usage_count = row[1]
        
        template = session.query(DocTemplateModel).filter_by(id=template_id).first()
        if template:
            template.count = usage_count
            update_count += 1
    
    session.commit()
    
    return {"code": 0, "msg": f"成功更新模板的使用计数", "data": {}}

@with_session
def doc_template_add(session,
                      name:str,
                      desc:str ,
                      role: str,
                      fromat_req: str,
                      user_email:str,
                      dep_id:int,
                      generate_info:List=None,
                      info: Dict = None,
                      
                      ) -> Dict:
    
    # db_obj = session.query(DocTemplateModel).filter_by(name=name).first()
    # db_obj
    # if db_obj:
    #     return {"code":-1,"msg":"已经存在","data":{}}
    obj = DocTemplateModel(name=name,desc=desc,role=role,fromat_req=fromat_req,user_email=user_email,generate_info=generate_info,info=info,dep_id=dep_id)
    session.add(obj)
    session.commit()
    #返回obj
    db_obj = session.query(DocTemplateModel).filter_by(name=name).first()

    # return {"code":0,"msg":"注册成功","user":{"username":user.username,"email":user.email,"role":user.role,"info":user.info,"create_time":user.create_time}}
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}





@with_session
def doc_template_update(session,
                    id:int,
                    name:str = None,
                    desc:str = None,
                    role: str = None,
                    fromat_req: str = None,
                    count:int = None,
                    generate_info:List= None,
                    info: Dict = None,
                    dep_id:int = None,
                      ) -> Dict:
    
    db_obj = session.query(DocTemplateModel).filter_by(id=id).first()
    
    if db_obj is None:
        return {"code":-1,"msg":"不存在该项数据","data":{}}
    if name:
        db_obj.name = name
    if desc:
        db_obj.desc = desc
    if role:
        db_obj.role = role
    if fromat_req:
        db_obj.fromat_req = fromat_req
    if count:
        db_obj.count = count
    if generate_info:
        db_obj.generate_info = generate_info
    if info:
        db_obj.info = info
    if dep_id:
        db_obj.dep_id = dep_id

    session.commit()
    # return {"code":0,"msg":"注册成功","user":{"username":user.username,"email":user.email,"role":user.role,"info":user.info,"create_time":user.create_time}}
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def doc_template_count_plus1(session,
                    id:int,
                      ) -> Dict:
    
    db_obj = session.query(DocTemplateModel).filter_by(id=id).first()
    db_obj.count = db_obj.count+1
    session.commit()
    # return {"code":0,"msg":"注册成功","user":{"username":user.username,"email":user.email,"role":user.role,"info":user.info,"create_time":user.create_time}}
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}

@with_session
def doc_template_delete(session,
                    id:int
                    ) -> Dict:
    
    db_obj = session.query(DocTemplateModel).filter_by(id=id).first()
    
    if db_obj is None:
        return {"code":-1,"msg":"不存在该项数据","data":{}}
    session.delete(db_obj)

    sql_delete_history = '''
    DELETE FROM doc_history 
    WHERE doc_template_id = :template_id
    '''

    params = {"template_id": id}
    session.execute(text(sql_delete_history), params)

    session.commit()

    # return {"code":0,"msg":"注册成功","user":{"username":user.username,"email":user.email,"role":user.role,"info":user.info,"create_time":user.create_time}}
    return {"code":0,"msg":"成功","data":{}}

@with_session
def doc_template_list(session,dep_id,name=None,page_start=None,page_end=None) -> Dict:
    
    db_objs = session.query(DocTemplateModel)

    if dep_id:
        db_objs =db_objs.filter_by(dep_id=dep_id)
    if name:
        db_objs = db_objs.filter(DocTemplateModel.name.like('%' + name + '%'))
        
    db_objs = db_objs.order_by(DocTemplateModel.id.desc())
    count=len(db_objs.all())
    
    db_objs = db_objs.slice(page_start,page_end).all()
    
    data =[db_obj.to_out_dict() for db_obj in  db_objs]
    
    # return {"code":0,"msg":"注册成功","user":{"username":user.username,"email":user.email,"role":user.role,"info":user.info,"create_time":user.create_time}}
    return {"code":0,"msg":"成功","data":{"count":count,"doc_templates":data}}


@with_session
def doc_template_detail(session,
                    id:int,
                    is_detail:bool=True
                    ) -> Dict:
    
    db_obj = session.query(DocTemplateModel).filter_by(id=id).first()
    
    if db_obj is None:
        return {"code":-1,"msg":"不存在该项数据"}

    # return {"code":0,"msg":"注册成功","user":{"username":user.username,"email":user.email,"role":user.role,"info":user.info,"create_time":user.create_time}}
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict(is_detail=is_detail)}
