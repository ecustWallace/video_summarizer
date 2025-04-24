from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class Test(Base):
    __tablename__ = 'test'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String, nullable=False)
    keyword = Column(String, nullable=False)
    number = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    summary = Column(String, nullable=True)
    status = Column(String, nullable=False, server_default='In Progress') 