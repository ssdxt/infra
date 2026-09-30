import uuid
from sqlalchemy import Column, DateTime, func, Uuid
from datetime import datetime, date
from decimal import Decimal

from db.session import Base


class BaseModel(Base):
    __abstract__ = True
    uuid = Column(Uuid, primary_key=True, index=True, default=uuid.uuid4)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def as_dict(self, exclude=None, include=None, convert_time=True):
        exclude = exclude or set()
        include = include or set(self.__table__.columns.keys())

        result = {}
        for key in include:
            if key in exclude:
                continue
            value = getattr(self, key, None)

            if convert_time and isinstance(value, (datetime, date)):
                value = value.isoformat() if value else None

            if isinstance(value, Decimal):
                value = float(value)
            if isinstance(value, str):
                try:
                    value = datetime.fromisoformat(value)
                except ValueError:
                    pass

            if isinstance(value, datetime):
                value = value.strftime("%Y-%m-%d %H:%M:%S")

            result[key] = value

        return result
