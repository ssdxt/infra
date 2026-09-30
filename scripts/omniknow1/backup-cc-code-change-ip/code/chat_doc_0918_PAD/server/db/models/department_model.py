import sys
sys.path.append("./")

from sqlalchemy import Column, Integer, String, DateTime, JSON, func, Boolean

from server.db.base import Base
from datetime import datetime
from server.db.repository.app_type_repository import app_type_detail, _app_type_name_list

class DepartmentModel(Base):
    """
    知识库模型
    """
    __tablename__ = 'department'
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键')
    name = Column(String(256), comment='')
    desc = Column(String(2048), comment='')
    parent_id = Column(Integer, default={})
    app_type_ids = Column(JSON, default={})
    theme_color = Column(String(32), default="#ff5c00", comment='主题色')
    app_count = Column(Integer, default=0, comment='应用数')
    info = Column(JSON, default={})

    def __repr__(self):
        return f"<DepartmentModel(id='{self.id}', name='{self.name}',desc='{self.desc},parent_id='{self.parent_id}',app_type_ids='{self.app_type_ids}',theme_color='{self.theme_color},app_count='{self.app_count}',info='{self.info}')>"

    def to_out_dict(self, is_detail=True):
        app_types = []
        if is_detail:
            if self.app_type_ids:
                app_types = _app_type_name_list(ids=self.app_type_ids)["data"]
                
        return {"id": self.id,
                "name": self.name,
                "desc": self.desc,
                "parent_id": self.parent_id,
                "app_types": app_types,
                "theme_color": self.theme_color,
                "app_count": self.app_count,
                "info": self.info
                }
