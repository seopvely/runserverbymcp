"""
SQLAlchemy 데이터베이스 모델
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from datetime import datetime

# Base 클래스 생성
Base = declarative_base()

class Server(Base):
    """서버 정보 테이블"""
    __tablename__ = 'servers'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='서버 ID')
    title = Column(String(255), nullable=False, comment='서버 제목')
    host = Column(String(255), nullable=False, comment='서버 IP/호스트명')
    port = Column(Integer, default=22, comment='SSH 포트')
    username = Column(String(100), default='root', comment='SSH 사용자명')
    description = Column(Text, comment='서버 설명')
    created_at = Column(DateTime, default=func.now(), comment='생성일시')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='수정일시')
    
    # 복합 유니크 제약
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )
    
    def __repr__(self):
        return f"<Server(id={self.id}, title='{self.title}', host='{self.host}:{self.port}')>"
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            'title': self.title,
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'name': f"{self.username}@{self.host}"  # 호환성을 위해
        }

# MySQL 연결 설정
MYSQL_CONFIG = {
    'host': '192.168.0.10',
    'user': 'runmcp',
    'password': 'rcpGsy2*dmQ',
    'database': 'runmcp',
    'charset': 'utf8mb4'
}

def get_database_url():
    """데이터베이스 URL 반환"""
    return f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@{MYSQL_CONFIG['host']}/{MYSQL_CONFIG['database']}?charset={MYSQL_CONFIG['charset']}"

def create_db_engine():
    """SQLAlchemy 엔진 생성"""
    return create_engine(
        get_database_url(),
        echo=False,  # SQL 쿼리 로깅 (개발 시에는 True)
        pool_pre_ping=True,  # 연결 상태 확인
        pool_recycle=3600,   # 1시간마다 연결 재생성
    ) 
