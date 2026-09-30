from pydantic import (
    BaseModel,
    UUID4,
    Field,
    ConfigDict
)


class EntSchema(BaseModel):
    name: str = Field(...,
                      description="企业名称",
                      examples=["炽橙科技"]
    )
    description: str = Field(None,
                             description="企业描述",
                             examples=["这是一家XX公司"]
    )
    logo: str = Field(None,
                    description="企业logo",
                    examples=["https://xx.com/logo.png"]
    )
    contact: str = Field(None,
                     description="企业联系人",
                     examples=["张三"]
    )
    version: int = Field(0,
                     description="企业版本",
                     examples=[0, 1, 2, 3]
    )


class UpdateEntSchema(BaseModel):
    name: str = Field(None,
                      description="企业名称",
                      examples=["炽橙科技"]
    )
    description: str = Field(None,
                             description="企业描述",
                             examples=["这是一家XX公司"]
    )
    logo: str = Field(None,
                    description="企业logo",
                    examples=["https://xx.com/logo.png"]
    )
    contact: str = Field(None,
                     description="企业联系人",
                     examples=["张三"]
    )
    version: int = Field(0,
                     description="企业版本",
                     examples=[0, 1, 2, 3]
    )