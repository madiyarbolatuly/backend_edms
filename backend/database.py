from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models.base import Base
from . import settings


SQLALCHEMY_DATABASE_URL = settings.database_url


engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
