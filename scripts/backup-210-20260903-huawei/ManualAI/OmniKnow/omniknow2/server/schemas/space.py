from pydantic import BaseModel, Field

from uuid import UUID


class SpaceCreateSchema(BaseModel):
    name: str | None = Field("默认空间",
                      examples=["测试空间"])
    logo: str | None = Field("",
                      examples=["https://example.com/logo.png"])
    description: str | None = Field("",
                          examples=["这是一个测试空间"])


class SpaceCreateReponseSchema(BaseModel):
    uuid: UUID = Field(...,
                      examples=["1234567890"])
    name: str = Field(...,
                      examples=["默认空间"])
    description: str | None = Field("",
                          examples=["这是一个测试空间"])
    logo: str | None = Field("",
                      examples=["https://example.com/logo.png"])
    code: str = Field(...,
                      examples=["1234567890"])


class SpaceUpdateSchema(BaseModel):
    space_uuid: UUID = Field(...,
                             examples=["123e4567-e89b-12d3-a456-426614174000"])
    name: str | None = Field(None,
                      examples=["测试空间"])
    logo: str | None = Field(None,
                      examples=["https://example.com/logo.png"])
    description: str | None = Field(None,
                          examples=["这是一个测试空间"])


class SpaceInviteSchema(BaseModel):
    account: str = Field(...,
                         alias="account",
                         description="被邀请用户的账号",
                         examples=['admin', 'test_user'])
    # space_uuid: UUID = Field(...,
    #                          alias="space_uuid",
    #                          description="空间UUID",
    #                          examples=['123e4567-e89b-12d3-a456-426614174000'])


class SpaceMemberRoleUpdateRequest(BaseModel):
    role: str = Field(...,
                      description="新角色：owner/admin/member/viewer",
                      examples=["admin", "member"])