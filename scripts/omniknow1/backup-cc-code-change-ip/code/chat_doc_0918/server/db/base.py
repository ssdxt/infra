from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.orm import sessionmaker

from configs import SQLALCHEMY_DATABASE_URI
import json


js = lambda obj: json.dumps(obj, ensure_ascii=False)
engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    json_serializer= js,
    pool_size=5,max_overflow=10
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base: DeclarativeMeta = declarative_base()
