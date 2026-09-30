from pydantic import BaseModel


class ResourceGrantSchema(BaseModel):
    resource_uuid: str
    grant_type: str