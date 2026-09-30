from pydantic import (
    BaseModel,
    Field,
)
from typing import Optional, Any


class AuthRequest(BaseModel):
    api_key: str = Field(...,
                        alias="api_key",
                        description="API Key",
                        examples=['ZJU_CLOUD_API']
                        )
    api_secret: str = Field(...,
                            alias="secret_key",
                            description="Secret Key",
                            examples=['3efad69b901f9ed9878faa1f69757a4b3b9202d6cd866fc0ab2ebaca9b4dccab973e3ce5285533cd3fd0380d2440ce3f30400762a996871a3440d67b0c1b5816']
                            )


class Token(BaseModel):
    access_token: str
    token_type: str


class ResponseModel(BaseModel):
    code: int
    message: str
    data: Optional[Any]

    @classmethod
    def success(cls, data=None, message="success", code=200):
        return cls(code=code, message=message, data=data).model_dump()

    @classmethod
    def fail(cls, message="error", code=1099):
        return cls(code=code, message=message, data=None).model_dump()