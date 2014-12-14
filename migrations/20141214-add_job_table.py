"""
"""
import os
import json
from sqlalchemy import (create_engine, Table, Column, String, Integer,
                        PickleType, Boolean, DateTime, Float, Text,
                        MetaData, select, ForeignKey, bindparam,
                        delete, and_)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from config import Configuration

Base = declarative_base()

engine = create_engine(Configuration.SQLALCHEMY_DATABASE_URI, echo=True)

metadata = MetaData()


class Job(Base):
    __tablename__ = 'job'

    id = Column(Integer, primary_key=True)
    created = Column(DateTime, default=func.now())
    updated = Column(DateTime, onupdate=func.now())
    key = Column(String(128))
    params = Column(PickleType)
    result = Column(PickleType)
    complete = Column(Boolean)


metadata.create_all(engine)
