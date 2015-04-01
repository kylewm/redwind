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

engine = create_engine(Configuration.SQLALCHEMY_DATABASE_URI, echo=True)

engine.execute('alter table post add column start datetime')
engine.execute('alter table post add column end datetime')
engine.execute('alter table post add column updated datetime')
