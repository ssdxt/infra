from server.db.models.user_info_model import UserInfoModel
from server.db.session import with_session
from server.knowledge_base.utils import KnowledgeFile
from typing import List, Dict
import uuid
import base64
# from passlib.context import CryptContext
# import jwt


__pw_salt ="lb@cc"

@with_session
def user_register(session,
                  email:str,
                  password: str,
                  username: str,
                  activate:bool,
                  dep_id:int,
                  role:int,
                  sex:str,
                  phone_num:str,
                  job_title:str,
                  app_ids:list
                  ) -> Dict:
    user = session.query(UserInfoModel).filter_by(username=username).first()
    if user:
        return {"code":-1,"msg":"该用户名已创建","data":{}}
    
    user_email = session.query(UserInfoModel).filter_by(email=email).first()
    if user_email:
        return {"code":-1,"msg":"该邮箱已注册","data":{}}

    password = __pw_salt+password
    password = base64.b64encode(password.encode("utf-8")).decode("utf-8")
    obj = UserInfoModel(email=email,password=password,username=username,activate=activate,dep_id=dep_id,role=role,sex=sex,phone_num=phone_num,job_title=job_title,app_ids=app_ids)
    session.add(obj)
    session.commit()
    
    user = session.query(UserInfoModel).filter_by(email=email).first()
    return {"code":0,"msg":"成功","data":user.to_out_dict()}
    
# @with_session
# def user_password_update(session,email,password) -> bool:
#     user = session.query(UserInfoModel).filter_by(email=email).first()
#     password = __pw_salt+password
#     password = base64.b64encode(password.encode("utf-8")).decode("utf-8")
#     user.password = password
#     session.commit()
#     return {"code":0,"msg":"成功","data":user.to_out_dict()}
    
@with_session
def user_update(session,email:str,
                  password: str,
                  username: str,
                  activate:bool,
                  dep_id:int,
                  role:int,
                  sex:str,
                  phone_num:str,
                  job_title:str,
                  app_ids:list) -> List[Dict]:
    user = session.query(UserInfoModel).filter_by(email=email).first()
    if user is None:
        return {"code":-1,"msg":"用户信息错误","data":{}}
    if username is not None:
        user_name = session.query(UserInfoModel).filter_by(username=username).first()
        if user_name:
            return {"code":-1,"msg":"该用户名已存在","data":{}}
        user.username = username
    if password is not None:
        password = __pw_salt+password
        password = base64.b64encode(password.encode("utf-8")).decode("utf-8")
        user.password = password
    if activate is not None:
        user.activate = activate
    if dep_id is not None:
        user.dep_id = dep_id
    if role is not None:
        user.role = role
    if sex is not None:
        user.sex = sex
    if phone_num is not None:
        user.phone_num = phone_num
    if job_title is not None:
        user.job_title = job_title   
    if app_ids is not None:
        user.app_ids = app_ids
    
    session.commit()
    return {"code":0,"msg":"成功","data":user.to_out_dict()}

@with_session
def user_login(session,
                      username: str,
                      password: str ,
                      ) -> List[Dict]:
    user = session.query(UserInfoModel).filter_by(username=username).first()

    if user is None:
        return {"code":-1,"msg":"用户不存在","data":{}}

    decoded_password = base64.b64decode(password).decode('utf-8')
    prefix = f"{username}_"
    temp_password = decoded_password[len(prefix):]
    last_underscore_index = temp_password.rfind('_')
    if last_underscore_index != -1:
        actual_password = temp_password[:last_underscore_index]

    password = __pw_salt+actual_password
    password = base64.b64encode(password.encode("utf-8")).decode('utf-8')
#    password = base64.b64encode(password.encode("utf-8")).decode("utf-8")
    
    if user.password != password:
        return {"code":-1,"msg":"账号密码错误","data":{}}
    elif user.activate == False:
        return {"code":-1,"msg":"用户被停用","data":{}}
    else:
        return {"code":0,"msg":"成功","data":user.to_out_dict()}


@with_session
def get_user(session, email: str,is_detail=True ) -> List[Dict]:
    user = session.query(UserInfoModel).filter_by(email=email).first()
    if user is None:
        return {"code":-1,"msg":"用户信息错误","data":{}}
    else:
        return {"code":0,"msg":"成功","data":user.to_out_dict(is_detail)}

@with_session
def user_list(session,email,username,role,dep_id,page_start,page_end):
    _users = session.query(UserInfoModel)
    
    if dep_id :
        _users = _users.filter(UserInfoModel.dep_id==dep_id)
    if email:
        _users = _users.filter(UserInfoModel.email.like('%'+email+'%'))
    if username:
        _users = _users.filter(UserInfoModel.username.like('%'+username+'%'))
    if role :
        _users = _users.filter(UserInfoModel.role==role)
    
    _users = _users.order_by(UserInfoModel.id.desc())

    count = len(_users.all())
    
    _users = _users.slice(page_start,page_end).all()
    data =[]
    
    for _user in _users:
        data.append(_user.to_out_dict())
  
    return {"code":0,"msg":"成功","data":{"users":data,"count":count}}

from sqlalchemy import text

@with_session
def user_history_delete(session, user_email: str):
    """
    删除 user_email 相关的所有记录信息
    """
    # 删除与 eval_history 相关的记录
    sql_delete_eval_history = '''
    DELETE FROM eval_history 
    WHERE user_email = :user_email
    '''
    session.execute(text(sql_delete_eval_history), {"user_email": user_email})

    # 删除与 test_history 相关的记录
    sql_delete_test_history = '''
    DELETE FROM test_history 
    WHERE user_email = :user_email
    '''
    session.execute(text(sql_delete_test_history), {"user_email": user_email})

    # 删除与 test_record 相关的记录
    sql_delete_test_record = '''
    DELETE FROM test_record 
    WHERE user_email = :user_email
    '''
    session.execute(text(sql_delete_test_record), {"user_email": user_email})

    session.commit()

    return {"code": 0, "msg": "用户相关记录删除成功"}

@with_session
def user_delete(session, user_email: str, current_role: int):

    user_info = session.query(UserInfoModel).filter_by(email=user_email).first()
    
    if user_info is None:
        return {"code": -1, "msg": "该数据不存在", "data": {}}

    if current_role == 1:
        session.delete(user_info)
        session.commit()
        user_history_delete(user_email)
        return {"code": 0, "msg": "成功", "data": {}}

    if user_info.role <= 2:
        return {"code": -1, "msg": "当前权限无法删除管理员用户", "data": {}}

    session.delete(user_info)
    session.commit()
    user_history_delete(user_email)
    return {"code": 0, "msg": "成功", "data": {}}

@with_session
def job_list(session, dep_id):
    db_objs = session.query(UserInfoModel).filter_by(dep_id=dep_id,role=3).order_by(UserInfoModel.id.desc()).all()
    
    if not db_objs:
        return {"code": -1, "msg": "数据不存在", "data": {}}
    
    job_titles = list({db_obj.job_title for db_obj in db_objs})
    
    return {"code": 0, "msg": "成功", "data": job_titles}

@with_session
def users_app_update(session, dep_id: int, old_job_titles: list, job_titles: list, app_id: int) -> Dict:

    updated_count = 0
    removed_count = 0
    
    if job_titles:
        new_users = session.query(UserInfoModel).filter(
            UserInfoModel.dep_id == dep_id,
            UserInfoModel.job_title.in_(job_titles)
        ).all()
        
        for user in new_users:
            current_app_ids = user.app_ids if user.app_ids else []
            
            if app_id not in current_app_ids:
                user.app_ids = current_app_ids + [app_id]
                updated_count += 1
    
    if old_job_titles:
        job_titles_to_remove = [jt for jt in old_job_titles if jt not in (job_titles or [])]
        
        if job_titles_to_remove:
            old_users = session.query(UserInfoModel).filter(
                UserInfoModel.dep_id == dep_id,
                UserInfoModel.job_title.in_(job_titles_to_remove)
            ).all()
            
            for user in old_users:
                current_app_ids = user.app_ids if user.app_ids else []
                
                # 如果应用ID在当前列表中，则移除
                if app_id in current_app_ids:
                    user.app_ids = [aid for aid in current_app_ids if aid != app_id]
                    removed_count += 1
    
    session.commit()
    
    return {"code": 0, "msg": "成功", "data": { f"成功为{updated_count}个用户添加应用权限，从{removed_count}个用户移除应用权限"}}

# @with_session
# def role_add(session,
#                       name:str,
#                       info: Dict = {},
#                       ) -> Dict:
    
#     user = session.query(UserRoleModel).filter_by(name=name).first()
#     if user:
#         return {"code":-1,"msg":"该权限已经添加","data":{}}
#     obj = UserRoleModel(name=name,info=info)
#     session.add(obj)
#     session.commit()
#     #返回obj
#     db_obj = session.query(UserRoleModel).filter_by(name=name).first()

#     # return {"code":0,"msg":"注册成功","user":{"username":user.username,"email":user.email,"role":user.role,"info":user.info,"create_time":user.create_time}}
#     return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


# @with_session
# def role_update(session,
#                     id:int,
#                       name:str,
#                       info: Dict = {},
#                       ) -> Dict:
    
#     db_obj = session.query(UserRoleModel).filter_by(id=id).first()
#     if db_obj is None:
#         return {"code":-1,"msg":"该权限已经存在","data":{}}
#     if name:
#         db_obj.name = name
#     if info:
#         db_obj.info = info

#     session.commit()
#     # return {"code":0,"msg":"注册成功","user":{"username":user.username,"email":user.email,"role":user.role,"info":user.info,"create_time":user.create_time}}
#     return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


# @with_session
# def role_delete(session,
#                     id:int,
#                     ) -> Dict:
    
#     db_obj = session.query(UserRoleModel).filter_by(id=id).first()
#     if db_obj is None:
#         return {"code":-1,"msg":"该权限不存在","data":{}}
#     session.delete(db_obj)
#     session.commit()

#     # return {"code":0,"msg":"注册成功","user":{"username":user.username,"email":user.email,"role":user.role,"info":user.info,"create_time":user.create_time}}
#     return {"code":0,"msg":"成功","data":{}}

# @with_session
# def role_list(session) -> Dict:
    
#     db_objs = session.query(UserRoleModel).all()
#     count=len(db_objs)
#     data =[db_obj.to_out_dict() for db_obj in  db_objs]
    
#     # return {"code":0,"msg":"注册成功","user":{"username":user.username,"email":user.email,"role":user.role,"info":user.info,"create_time":user.create_time}}
#     return {"code":0,"msg":"成功","data":{"count":count,"roles":data}}


# @with_session
# def role_detail(session,
#                     id:int,
#                     ) -> Dict:
    
#     db_obj = session.query(UserRoleModel).filter_by(id=id).first()
    
#     if db_obj is None:
#         return {"code":-1,"msg":"该权限不存在","data":{}}

#     # return {"code":0,"msg":"注册成功","user":{"username":user.username,"email":user.email,"role":user.role,"info":user.info,"create_time":user.create_time}}
#     return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}
