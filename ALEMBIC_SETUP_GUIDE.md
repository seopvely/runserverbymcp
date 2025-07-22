# 🗄️ Alembic 데이터베이스 마이그레이션 설정 완료

## 📋 개요

**Alembic** 데이터베이스 마이그레이션 시스템이 성공적으로 설정되었습니다!  
이제 체계적인 데이터베이스 스키마 버전 관리가 가능합니다.

## 🎯 완료된 설정

### ✅ 설치된 패키지
- `sqlalchemy` - ORM 및 데이터베이스 추상화
- `alembic` - 데이터베이스 마이그레이션 도구

### ✅ 생성된 파일들
```
📁 프로젝트 루트/
├── alembic.ini              # Alembic 설정 파일
├── 📁 alembic/
│   ├── env.py               # 환경 설정
│   ├── script.py.mako       # 마이그레이션 템플릿
│   ├── README               # 사용법 가이드
│   └── 📁 versions/
│       ├── __init__.py
│       └── 001_initial_servers_table.py  # 초기 테이블 마이그레이션
└── 📁 app/
    └── models.py            # SQLAlchemy 모델
```

## 🔧 설정 정보

### 데이터베이스 연결
```ini
# alembic.ini
sqlalchemy.url = mysql+pymysql://runmcp:rcpGsy2*dmQ@192.168.0.10/runmcp
```

### SQLAlchemy 모델
```python
# app/models.py
class Server(Base):
    __tablename__ = 'servers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=22)
    username = Column(String(100), default='root')
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

## 🚀 사용 방법

### 1. 라이브러리 설치
```bash
pip install sqlalchemy alembic
```

### 2. 현재 마이그레이션 상태 확인
```bash
# 현재 리비전 확인
alembic current

# 마이그레이션 히스토리 확인
alembic history --verbose
```

### 3. ⚡ 초기 마이그레이션 적용 (사용자가 실행)
```bash
# 데이터베이스에 servers 테이블 생성
alembic upgrade head
```

### 4. 새로운 마이그레이션 생성
```bash
# 모델 변경 후 자동 마이그레이션 생성
alembic revision --autogenerate -m "Add new column to servers"

# 빈 마이그레이션 파일 생성 (수동 작성)
alembic revision -m "Custom migration"
```

### 5. 마이그레이션 적용/롤백
```bash
# 최신 마이그레이션 적용
alembic upgrade head

# 한 단계 롤백
alembic downgrade -1

# 특정 리비전으로 이동
alembic upgrade 001
```

## 📊 초기 마이그레이션 (001_initial_servers_table.py)

### 생성되는 테이블 구조
```sql
CREATE TABLE servers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL COMMENT '서버 제목',
    host VARCHAR(255) NOT NULL COMMENT '서버 IP/호스트명',
    port INT NOT NULL DEFAULT 22 COMMENT 'SSH 포트',
    username VARCHAR(100) NOT NULL DEFAULT 'root' COMMENT 'SSH 사용자명',
    description TEXT COMMENT '서버 설명',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',
    UNIQUE KEY unique_server (host, port, username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

## 🔄 워크플로우

### 개발 사이클
1. **모델 변경** (`app/models.py` 수정)
2. **마이그레이션 생성** (`alembic revision --autogenerate`)
3. **마이그레이션 검토** (생성된 파일 확인/수정)
4. **마이그레이션 적용** (`alembic upgrade head`)
5. **테스트** (기능 동작 확인)

### 배포 사이클
1. **운영 DB 백업**
2. **마이그레이션 적용** (`alembic upgrade head`)
3. **애플리케이션 재시작**
4. **동작 확인**

## 🛡️ 안전 가이드

### ⚠️ 주의사항
- **프로덕션 적용 전 백업 필수**
- **마이그레이션 파일 검토 후 적용**
- **롤백 계획 수립**
- **테스트 환경에서 먼저 검증**

### 🔍 디버깅
```bash
# SQL 쿼리 로깅 활성화 (app/models.py에서 echo=True)
# 마이그레이션 dry-run (실제 실행 안함)
alembic upgrade head --sql

# 마이그레이션 정보 상세 확인
alembic show 001
```

## 📱 기존 FastAPI 애플리케이션과의 통합

현재 `app/main.py`는 **기존 PyMySQL 방식을 유지**합니다.  
Alembic은 **스키마 관리용**으로만 사용되며, 애플리케이션 로직은 변경되지 않습니다.

### 선택적 SQLAlchemy ORM 통합
원한다면 나중에 다음과 같이 SQLAlchemy ORM을 사용할 수 있습니다:

```python
# app/database.py (추가 생성 시)
from sqlalchemy.orm import sessionmaker
from app.models import create_db_engine

engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## 🎉 다음 단계

### 🚀 지금 바로 시작
```bash
# 1. 현재 상태 확인
alembic current

# 2. 초기 마이그레이션 적용 (사용자가 실행)
alembic upgrade head

# 3. 성공 확인
alembic current
# 출력: 001 (head)
```

### 🔮 향후 확장 가능성
- **다른 테이블 추가** (users, logs, configurations 등)
- **인덱스 최적화** 마이그레이션
- **데이터 마이그레이션** (기존 데이터 변환)
- **테이블 관계 설정** (Foreign Key 등)

---

🎊 **축하합니다!** Alembic 데이터베이스 마이그레이션 시스템이 완벽하게 설정되었습니다!

이제 `alembic upgrade head` 명령어를 실행하여 초기 테이블을 생성하세요. 
