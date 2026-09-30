from server.db.models.user_info_model import UserInfoModel
from server.db.models.doc_history_model import DocHistoryModel
from server.db.models.doc_template_model import DocTemplateModel
from server.db.session import with_session
from sqlalchemy.orm import aliased
from server.knowledge_base.utils import KnowledgeFile
from typing import List, Dict
from server.db.repository.user_info_repository import get_user
from server.db.repository.doc_template_repository import doc_template_detail


@with_session
def doc_history_add(session,
                      name:str,
                      desc:str,
                      content:str,
                      file_name:str ,
                      file_path:str,
                      doc_template_id:int,
                      user_email:str,
                      kb_ids:List,
                      keywords:Dict,
                      dep_id:int,
                    #   create_time:str,
                      doc_ref:Dict={},
                      info: Dict = {},
                      ) -> Dict:
    
    # db_obj = session.query(DocHistoryModel).filter_by(name=name).first()
    # if db_obj:
    #     return {"code":-1,"msg":"已经存在"}
    
    obj = DocHistoryModel(name=name,
                          desc = desc,
                          content = content,
                          file_name = file_name,
                          file_path = file_path,
                          doc_template_id = doc_template_id,
                          user_email = user_email,
                          kb_ids = kb_ids,
                          keywords = keywords,
                          dep_id=dep_id,
                          doc_ref=doc_ref,
                          info=info)
    session.add(obj)
    session.commit()
    #返回obj
    db_obj = session.query(DocHistoryModel).filter_by(name=name).first()

    # return {"code":0,"msg":"注册成功","user":{"username":user.username,"email":user.email,"role":user.role,"info":user.info,"create_time":user.create_time}}
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def doc_history_update(session,
                       id:int,
                      name:str=None,
                      desc:str=None,
                      content:str=None,
                      file_name:str =None,
                      file_path:str=None,
                      doc_template_id:int=None,
                      user_email:str=None,
                      kb_ids:List=None,
                      keywords:Dict=None,
                    #   create_time:str,
                      doc_ref:Dict = None,
                      info: Dict =None,
                      ) -> Dict:
    
    db_obj = session.query(DocHistoryModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在"}
    if name:
        db_obj.name = name
    if desc:
        db_obj.desc = desc
    if content:
        db_obj.content = content
    if file_name:
        db_obj.file_name = file_name  
    if file_path:
        db_obj.file_path = file_path
    if doc_template_id:
        db_obj.doc_template_id = doc_template_id
    if user_email:
        db_obj.user_email = user_email
    if kb_ids:
        db_obj.kb_ids = kb_ids
    if keywords:
        db_obj.keywords = keywords
    if doc_ref:
        db_obj.doc_ref = doc_ref
    if info:
        db_obj.info = info
    
    session.commit()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}

@with_session
def doc_history_list(session,dep_id,email,page_start,page_end) -> Dict:
    
    db_objs = session.query(DocHistoryModel)
    db_objs = db_objs.order_by(DocHistoryModel.id.desc())

    if dep_id:
        db_objs = db_objs.filter_by(dep_id=dep_id)

    if email:
        db_objs = db_objs.filter_by(user_email=email)
        
    count=len(db_objs.all())

    db_objs = db_objs.slice(page_start,page_end).all()

    data =[db_obj.to_out_dict() for db_obj in db_objs]
    return {"code":0,"msg":"成功","data":{"count":count,"dochistorys":data}}
    
    pass

@with_session
def doc_history_detail(session,
                    id:int,
                    ) -> Dict:
    
    db_obj = session.query(DocHistoryModel).filter_by(id=id).first()
    
    if db_obj is None:
        return {"code":-1,"msg":"不存在该项数据"}

    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}

@with_session
def doc_history_delete(session,
                    id:int,
                    ) -> Dict:
    
    db_obj = session.query(DocHistoryModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"该数据不存在","data":{}}
    session.delete(db_obj)
    session.commit()
    return {"code":0,"msg":"成功","data":{}}