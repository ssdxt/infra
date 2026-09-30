from datetime import datetime
from fastapi import Body
from server.utils import BaseResponse

def validate_expiration_time():
    """
    检查当前时间是否超过2025年12月25日
    如果超过，则返回过期信息
    """
    current_time = datetime.now()
    expiration_time = datetime(2025, 10, 18, 23, 59, 59)
    
    if current_time > expiration_time:
        return {
            "code": 403,
            "msg": "助手功能已过期，请联系管理员更新授权",
            "data": None
        }
    return None

def check_assistant_expiration():
    """
    检查助手是否过期的API函数
    可以单独调用此函数检查系统状态
    """
    result = validate_expiration_time()
    if result:
        return BaseResponse(code=result["code"], msg=result["msg"], data=None)
    return BaseResponse(code=200, msg="系统授权有效", data={"expiration_date": "2025-11-15"})
