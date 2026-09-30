from pydantic import (
    BaseModel,
    UUID4,
    Field,
    EmailStr,
    model_validator
)
from typing import Optional, Any
from datetime import datetime, date


character = ["超级管理员", "管理员", "普通用户"]

class UserLoginRequest(BaseModel):
    username: str = Field(...,
                        alias="username",
                        description="用户名",
                        examples=['admin', 'test_user', '123456']
                        )
    password: str = Field(...,
                        alias="password",
                        description="密码Base64编码",
                        examples=['isdjheq==']
                        )


class UserRegisterSchema(BaseModel):
    code: str = Field(...,
                        alias="code",
                        description="md5",
                        examples=['ksjfxlsqjspk']
                        )
    name: str = Field(...,
                        alias="name",
                        description="姓名",
                        examples=['张三']
                    )
    account: str = Field(...,
                        alias="account",
                        description="账号",
                        examples=['admin', 'admin@qq.com', '123456']
                        )
    password: str = Field(...,
                        alias="password",
                        description="密码Base64编码",
                        examples=['isdjheq==']
                        )


class UserSelfRegisterSchema(BaseModel):
    name: str = Field(...,
                      description="姓名",
                      examples=['张三'])
    account: str = Field(...,
                         description="账号",
                         examples=['zhangsan'])
    password: str = Field(...,
                          description="密码Base64编码",
                          examples=['isdjheq=='])


class UserProfileRequest(BaseModel):
    name: str = Field(None,
                    alias="name",
                    description="姓名",
                    examples=['张三']
                    )
    phone: str = Field(None,
                        alias="phone",
                        description="手机号",
                        examples=['12345678901']
                        )
    email: str = Field(None,
                        alias="email",
                        description="邮箱",
                        examples=['admin@qq.com']
                        )
    birthday: date = Field(None,
                        alias="birthday",
                        description="生日",
                        examples=['2023-01-01']
                        )
    sex: int = Field(None,
                        alias="sex",
                        description="性别",
                        examples=[0, 1]
                        )


class UserProfileResponse(BaseModel):
    # 显式声明需要的字段，自动过滤掉 password, salt 等敏感字段
    space_id: UUID4
    space_role: str
    uuid: UUID4
    account: str
    name: str | None
    phone: str | None = None
    email: str | None = None
    source: str
    roles: list[str] = []
    department: Optional[str] = None
    position: Optional[str] = None
    tenant: Optional[str] = None
    birthday: Optional[date] = None

    created_at: datetime

    # 可以自定义序列化配置，比如时间格式
    class Config:
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S"),
            date: lambda v: v.strftime("%Y-%m-%d")
        }


class CurrentUser(BaseModel):
    uuid: UUID4 = Field(...,
                        alias="uuid",
                        description="用户ID",
                        examples=['xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx']
                        )
    source: str = Field(...,
                        alias="source",
                        description="注册来源",
                        examples=['本地注册']
                        )