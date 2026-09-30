from server.db.repository.user_info_repository import UserInfoModel,user_register,user_login,user_update,get_user,user_list,job_list,user_delete,users_app_update
from server.utils import BaseResponse, ListResponse
from fastapi import Body,Form,Request,Response,Depends,Header,HTTPException,status
from datetime import datetime,timedelta
from typing import Optional
import jwt
from pydantic import Json
import time

__g_token_user_set ={}

SECRET_KEY = "Y2MtdGVjaC5jb20gbGI="
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 7*24*60

# <email,[token,user_dict]>
def update_token(email,token,user):
    if token:
        __g_token_user_set[email] = {"token":token,"user":user}
    else:
         __g_token_user_set[email] = None



def get_current_token(email):
    playload = __g_token_user_set.get(email)
    if playload:
        token =  playload.get("token")
        return token
    else:
        return None

def get_current_user(email):
    playload = __g_token_user_set.get(email)
    if playload:
        return playload.get("user")
    else:
        return None



def is_super_admin(user_dict):
    if user_dict["user"] is None:
        return False
    role = user_dict["user"]["role"]
    if role == 1:
        return True
    else:
        return False
    
    

def is_admin(user_dict):
    if user_dict["user"] is None:
        return False
    role = user_dict["user"]["role"]
    if role == 2:
        return True
    else:
        return False

import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLACKLIST_CONFIG_FILE = os.path.join(PROJECT_ROOT, "configs", "blacklist_config.json")

def load_blacklist():
    """从JSON文件加载黑名单"""
    if os.path.exists(BLACKLIST_CONFIG_FILE):
        with open(BLACKLIST_CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('BLACKLIST_USER', [])
    return []

def save_blacklist(blacklist):
    """保存黑名单到JSON文件"""
    config = {'BLACKLIST_USER': blacklist}
    with open(BLACKLIST_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def invalidate_user_tokens(email):
    """强制指定用户登出"""
    BLACKLIST_USER = load_blacklist()
    # 直接将用户邮箱加入黑名单
    if email not in BLACKLIST_USER:
        BLACKLIST_USER.append(email)
    print(f"User {email} added to logout blacklist")
    
    # 同步保存到文件
    save_blacklist(BLACKLIST_USER)
    
    # 清除该用户的缓存
    update_token(email, None, None)
    print(f"User blacklist content: {BLACKLIST_USER}")

def token_check(request: Request,response:Response,token: Optional[str] = Header(...)) -> dict:
    #token依赖请求头的token校验
    # #验证失败返回信息
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="验证失败"
    )
    # #未登录失效的信息
    credentials_FOR_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="用户未登录或者登陆token已经失效"
    )

    try:
        #解析token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        expire = payload["exp"]
        token_email = payload["email"]

        BLACKLIST_USER = load_blacklist()
        # print(f"检查用户: {token_email}")
        # print(f"当前黑名单: {BLACKLIST_USER}")
        if token_email in BLACKLIST_USER:
            # print("用户在黑名单中，应该被拒绝")
            raise credentials_FOR_exception

        # if get_current_token(token_email) is None:
        #     raise credentials_FOR_exception
        user = get_current_user(token_email)
        if user is None:
            user = get_user(token_email,is_detail=False).get("data")
        
        if user.get("email") is None or user.get("activate") == False:
            raise credentials_FOR_exception
        
        # print("expire",expire )
        expire = int(expire)
        # print("expire-time.time()",expire-time.time(),ACCESS_TOKEN_EXPIRE_MINUTES/7*60)

        if expire-time.time() <ACCESS_TOKEN_EXPIRE_MINUTES/7*60:
            new_token = create_access_token({"email":token_email})
            response.headers["token"] = new_token
            #更新新token
            update_token(token_email,new_token,user)
        else:
            pass
        return {"user":user} 
    except Exception as e:
        print("token_check....")
        print(e)
        if e == credentials_FOR_exception:
            raise credentials_FOR_exception
        raise credentials_exception

def admin_token_check(request: Request,response:Response,token: Optional[str] = Header(...)) -> dict:
    #token依赖请求头的token校验
    # #验证失败返回信息
    user_dict = token_check(request,response,token)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="验证失败"
    )
    
    user = user_dict["user"]
    role = user["role"]
    if role >2:
        raise credentials_exception
    # print("user_dict>>>>",user_dict)
    return user_dict
    
    

# 生成token
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
     
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 更新到我们之前传进来的字典
    to_encode.update({"exp": expire})
    # jwt 编码 生成我们需要的token
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    print("create_access_token",encoded_jwt,to_encode)
    return encoded_jwt


from pydantic import BaseModel
class AddParams(BaseModel):
    email:str 
    username:str
    password:str
    # create_time
    activate:bool= True
    dep_id:int
    role:int
    sex:str=None
    phone_num:str = None
    job_title:str
    app_ids:list = None
    # info:dict =None

#注册用户

def register_api(params:AddParams
) -> BaseResponse:
    user = user_register(email=params.email,
                         username=params.username,
                         password=params.password,
                         activate=params.activate,
                         dep_id = params.dep_id,
                         role=params.role,
                         sex=params.sex,
                         phone_num = params.phone_num,
                         job_title=params.job_title,
                         app_ids=params.app_ids,
                        )
    if user["code"] >=0:
        user = user["data"]
        data = {"email":user["email"]}
        token = create_access_token(data)
        update_token(user["email"],token,user)
        response = BaseResponse(code=200, msg=f"更新成功",data={"token":token})
        return response
    else :
        return BaseResponse(code=user["code"],msg=user["msg"],data={})
    
#用户登录
def login_api(
        username:str = Body(..., description="用户名", examples=["samples"]),
        password: str = Body(..., description="密码", examples=["samples"])
)-> BaseResponse:
    user = user_login(username=username,password=password)
    
    if user["code"] >=0 :

        user = user["data"]
        data = {"email":user["email"]}
        email = user["email"]
        
        login_token = get_current_token(email)
        
        if login_token:
            try:
                payload = jwt.decode(login_token, SECRET_KEY, algorithms=[ALGORITHM])
                expire = payload["exp"]
                if int(expire)-time.time() >300:
                    response = BaseResponse(code=200, msg=f"登录成功",data={"token":login_token})
                    return response
            except Exception:
                pass
    
        token = create_access_token(data)
        update_token(user["email"],token,user)

        BLACKLIST_USER = load_blacklist()
        if user["email"] in BLACKLIST_USER:
            BLACKLIST_USER.remove(user["email"])
            save_blacklist(BLACKLIST_USER)

        response = BaseResponse(code=200, msg=f"更新成功",data={"token":token})
        return response
    else :
        return BaseResponse(code=user["code"],msg=user["msg"],data={})
    
#用户获取自己的信息
def current_user_info(
        current_user_dict=Depends(token_check)
)-> BaseResponse:
    user = current_user_dict["user"]
    email = user["email"]
    response_dict = get_user(email)
    reponse = BaseResponse(code=response_dict["code"],msg=response_dict["msg"],data={"user":response_dict["data"]})
    return reponse



class QueryUserInfoModel(BaseModel):
    email:str

#管理员获取用户信息
def user_info(params:QueryUserInfoModel,current_user_dict=Depends(admin_token_check)
)-> BaseResponse:
    
    current_user = current_user_dict["user"]
    current_email = current_user["email"]
    current_user_role =current_user["role"]

    response_dict = get_user(params.email)
    reponse = BaseResponse(code=response_dict["code"],msg=response_dict["msg"],data={"user":response_dict["data"]})
    return reponse

#更新当前用户的信息


class UpdateParams(BaseModel):
    # email:str 
    username:str = None
    password:str = None
    # create_time
    # activate:bool= True
    # dep_id:int=None
    # role:int = 3
    sex:str=None
    phone_num:str = None
    job_title:str= None
    # app_ids:list = None

def update_current_user(params:UpdateParams,current_user_dict=Depends(token_check)
)-> BaseResponse:

    user = current_user_dict["user"]
    email = user["email"]
    # email:str,
    # password: str,
    # username: str,
    # activate:bool,
    # dep_id:int,
    # role:int,
    # sex:str,
    # phone_num:str,
    # job_title:str,
    # app_ids:list
    
    need_invalidate_token = params.username is not None or params.password is not None

    response_dict = user_update(email,password=params.password,username=params.username,activate=None,dep_id=None,role=None,sex=params.sex,phone_num=params.phone_num,job_title=params.job_title,app_ids=None)

    if need_invalidate_token and response_dict["code"] == 0:
        invalidate_user_tokens(email)

    reponse = BaseResponse(code=response_dict["code"],msg=response_dict["msg"],data={"user":response_dict["data"]})
    return reponse


class AdminUpdateParams(BaseModel):
    email:str 
    password: str=None
    username: str=None
    activate:bool=None
    dep_id:int=None
    role:int=None
    sex:str=None
    phone_num:str=None
    job_title:str=None
    app_ids:list=None

#管理员更新
def update_user(
    params:AdminUpdateParams,
    current_user_dict=Depends(admin_token_check)
)-> BaseResponse:

    need_invalidate_token = params.username is not None or params.password is not None

    response_db = user_update(email=params.email,password=params.password,username=params.username,activate=params.activate,dep_id=params.dep_id,role=params.role,sex=params.sex,phone_num=params.phone_num,job_title=params.job_title,app_ids=params.app_ids)
    
    # if response_db["code"]==0:
    #     update_token(params.email,get_current_token(params.email),response_db["data"])
    if need_invalidate_token and response_db["code"] == 0:
        invalidate_user_tokens(params.email)
        
    reponse = BaseResponse(code=response_db["code"],msg=response_db["msg"])
    return reponse

class ListParams(BaseModel):
    dep_id:int=None
    email:str=None
    username:str=None
    role:int= None
    page_no:int = 1
    page_size:int = 20
    
#管理查看所有用户信息
def list_user(params:ListParams,current_user_dict=Depends(admin_token_check))->BaseResponse:
    current_user = current_user_dict["user"]
    email = current_user["email"]
    role = current_user["role"]
    dep_id = current_user["dep_id"]
    
    dep_id_param = None
    if role == 1 :
        #超管这个权限才有用
        dep_id_param = None
        if params.dep_id:
            dep_id_param = params.dep_id
    else:
        dep_id_param = dep_id
        

    page_start = (params.page_no-1) * params.page_size
    page_end = page_start+params.page_size
    response_dict = user_list(email=params.email,username=params.username,role=params.role,dep_id=dep_id_param,page_start=page_start,page_end=page_end)
    response = BaseResponse(code=response_dict["code"],msg=response_dict["msg"],data=response_dict["data"])
    return response

from typing import List

class DeleteParams(BaseModel):
    user_emails: List[str]

#管理删除所有用户信息
def delete_user(params:DeleteParams,current_user_dict=Depends(admin_token_check))->BaseResponse:
    current_user = current_user_dict["user"]
    current_role = current_user["role"]

    success = []
    failure = []

    for user_email in params.user_emails:
        db_obj = user_delete(user_email=user_email,current_role=current_role)

        if db_obj["code"] == 0:
            success.append(user_email)
        else:
            failure.append({"email": user_email, "msg": db_obj["msg"]})

    return BaseResponse(code=0,msg="无权限删除管理员账户" if failure else "用户删除成功",data={"成功删除": success, "无法删除": failure})

class JobListParams(BaseModel):
    dep_id:int = None

#获取当前单位注册用户的所有岗位
def list_job(params:ListParams,user_dict=Depends(token_check))->BaseResponse:
    current_user = user_dict["user"]
    email = current_user["email"]
    role = current_user["role"]
    user_dep_id = current_user["dep_id"]

    if is_super_admin(user_dict=user_dict):
        dep_id = params.dep_id
    else:
        dep_id = user_dep_id
        
    db_obj = job_list(dep_id=dep_id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

from server.db.repository.app_repository import app_job_update

class UpdateUsersAppParams(BaseModel):
    dep_id:int = None
    job_titles:List[str]
    app_id:int

def update_user_app(params:UpdateUsersAppParams,user_dict=Depends(token_check))->BaseResponse:
    current_user = user_dict["user"]
    user_dep_id = current_user["dep_id"]

    if is_super_admin(user_dict=user_dict):
        dep_id = params.dep_id
    else:
        dep_id = user_dep_id

    old_job_titles=app_job_update(id=params.app_id,job_titles=params.job_titles)

    db_obj = users_app_update(dep_id=dep_id, old_job_titles=old_job_titles, job_titles=params.job_titles, app_id=params.app_id)

    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

# class AddRoleModel(BaseModel):
#     name:str=None
#     info:dict={}

# def add_role(arm:AddRoleModel,current_user_dict=Depends(token_check)
# ) -> BaseResponse:
#     current_user = current_user_dict["user"]
#     current_email = current_user["email"]
    
#     db_obj = role_add(name=arm.name,info=arm.info)
#     if db_obj["code"] >=0:
#         db_obj = db_obj["data"]
#         response = BaseResponse(code=200, msg=f"更新成功",data={"role":db_obj})
#         return response
#     else :
#         return BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data={})
    
# class UpdateRoleModel(BaseModel):
#     role:int
#     name:str=None
#     info:dict={}
    
# def update_role(urm:UpdateRoleModel,current_user_dict=Depends(token_check)
# ) -> BaseResponse:
#     current_user = current_user_dict["user"]
#     current_email = current_user["email"]
    
#     if urm.role == None:
#         return BaseResponse(code=-1,msg="role 不能为空",data={})
    
#     db_obj = role_update(id=urm.role,name=urm.name,info=urm.info)
#     if db_obj["code"] >=0:
#         db_obj = db_obj["data"]
#         response = BaseResponse(code=200, msg=f"更新成功",data={"role":db_obj})
#         return response
#     else :
#         return BaseResponse(code=db_obj["code"] ,msg=db_obj["msg"],data={})
    
# def list_role(current_user_dict=Depends(token_check)
# ) -> BaseResponse:
#     db_obj = role_list()
#     if db_obj["code"] >=0:
#         response = BaseResponse(code=200, msg=f"更新成功",data=db_obj["data"])
#         return response
#     else :
#         return BaseResponse(code=200,msg=db_obj["msg"],data={})
    
    
# class DeleteRoleModel(BaseModel):
#     role:int =-1

# def detail_role(drm:DeleteRoleModel,current_user_dict=Depends(token_check)
# ) -> BaseResponse:
#     if drm is None or drm.role is None or drm.role ==-1:
#         return BaseResponse(code=-1,msg="role 不能为空",data={})
#     db_obj = role_detail(id= drm.role)
#     if db_obj["code"] >=0:
#         response = BaseResponse(code=200, msg=f"更新成功",data=db_obj["data"])
#         return response
#     else :
#         return BaseResponse(code=db_obj["code"] ,msg=db_obj["msg"],data={})

# def delete_role(drm:DeleteRoleModel,current_user_dict=Depends(token_check)
# ) -> BaseResponse:
#     if drm is None or drm.role is None or drm.role ==-1:
#         return BaseResponse(code=-1,msg="role 不能为空",data={})
#     db_obj = role_delete(id= drm.role)
#     if db_obj["code"] >=0:
#         response = BaseResponse(code=200, msg=f"更新成功",data=db_obj["data"])
#         return response
#     else :
#         return BaseResponse(code=db_obj["code"] ,msg=db_obj["msg"],data={})

