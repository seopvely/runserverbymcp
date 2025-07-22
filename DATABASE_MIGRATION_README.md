# 🚀 MySQL 데이터베이스 마이그레이션 완료

## 📋 개요

SSH 서버 관리 시스템이 SQLite에서 **MySQL**로 성공적으로 마이그레이션되었습니다!  
이제 더 강력하고 안정적인 데이터베이스 시스템을 사용합니다.

## 🔧 MySQL 연결 설정

### 데이터베이스 정보
```
🏠 호스트: 192.168.0.10
👤 사용자: runmcp  
🗄️ 데이터베이스: runmcp
🔐 비밀번호: rcpGsy2*dmQ
```

### 연결 설정 (app/main.py)
```python
MYSQL_CONFIG = {
    'host': '192.168.0.10',
    'user': 'runmcp',
    'password': 'rcpGsy2*dmQ',
    'database': 'runmcp',
    'charset': 'utf8mb4',
    'autocommit': True
}
```

## 📊 데이터베이스 스키마

### `servers` 테이블
```sql
CREATE TABLE servers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,                    -- 서버 제목
    host VARCHAR(255) NOT NULL,                     -- 서버 IP/호스트명
    port INT DEFAULT 22,                            -- SSH 포트
    username VARCHAR(100) DEFAULT 'root',           -- SSH 사용자명
    description TEXT,                               -- 서버 설명
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 생성일시
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_server (host, port, username) -- 중복 방지
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

## 🛠️ 설치 및 설정

### 1. MySQL 라이브러리 설치
```bash
pip install pymysql
```

### 2. MySQL 서버 준비
- MySQL 서버가 192.168.0.10에서 실행 중이어야 함
- `runmcp` 데이터베이스가 존재해야 함
- `runmcp` 사용자 권한 설정 필요

### 3. 데이터베이스 연결 테스트
```bash
python test_mysql_connection.py
```

## ✨ 주요 변경사항

### 🔄 SQLite → MySQL 마이그레이션
- **연결 방식**: `sqlite3` → `pymysql`
- **데이터 타입**: `INTEGER` → `INT`, `TEXT` → `VARCHAR/TEXT`
- **자동증가**: `AUTOINCREMENT` → `AUTO_INCREMENT`
- **파라미터 바인딩**: `?` → `%s`
- **시간 함수**: `CURRENT_TIMESTAMP` → `NOW()`

### 🎯 개선된 기능
- **더 나은 성능**: MySQL의 최적화된 쿼리 엔진
- **동시성 지원**: 여러 사용자가 동시에 접근 가능
- **확장성**: 대용량 데이터 처리 가능
- **안정성**: 트랜잭션과 롤백 지원
- **백업**: MySQL 표준 백업 도구 활용

### 🔐 보안 강화
- **네트워크 분리**: 원격 MySQL 서버 사용
- **사용자 권한**: 전용 데이터베이스 사용자
- **데이터 무결성**: UNIQUE 제약 조건
- **문자셋**: UTF8MB4로 완전한 유니코드 지원

## 🚦 애플리케이션 시작

### 정상 시작
```bash
# 애플리케이션 시작
python app/main.py

# 또는 uvicorn 사용
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 로그 확인
앱 시작 시 다음과 같은 로그가 표시됩니다:
```
✅ MySQL 데이터베이스가 성공적으로 초기화되었습니다.
```

### 연결 실패 시
```
❌ MySQL 연결 실패: ...
💥 데이터베이스 초기화 중 심각한 오류: ...
   MySQL 서버가 실행 중이고 연결 정보가 올바른지 확인해주세요.
   연결 정보: runmcp@192.168.0.10:3306/runmcp
```

## 📱 웹 인터페이스 사용법

### 1. 서버 등록
1. **서버 접근 생성** 탭으로 이동
2. **🏷️ 저장 타이틀** 입력 (예: "운영-웹서버01")
3. **📝 설명** 입력 (선택사항)
4. 서버 정보 입력 (IP, 포트, 사용자명, 비밀번호)
5. **🚀 SSH 키 설치 및 서버 등록** 클릭

### 2. 서버 관리
- **서버 정보** 탭에서 등록된 서버들 확인
- **🔗 빠른 접속**: 세션 모드로 바로 이동
- **🔍 연결 테스트**: 서버 상태 확인
- **🗑️ 삭제**: 불필요한 서버 제거

### 3. 서버 접속
- **세션 모드**: 지속적인 SSH 연결로 여러 명령 실행
- **터미널**: 실시간 대화형 쉘 환경
- **단일 명령어**: 빠른 일회성 명령 실행

## 🔧 관리 및 유지보수

### MySQL 백업
```bash
mysqldump -h 192.168.0.10 -u runmcp -p runmcp > servers_backup.sql
```

### MySQL 복원
```bash
mysql -h 192.168.0.10 -u runmcp -p runmcp < servers_backup.sql
```

### 테이블 상태 확인
```sql
-- 서버 목록 조회
SELECT * FROM servers ORDER BY created_at DESC;

-- 테이블 구조 확인
DESCRIBE servers;

-- 인덱스 정보
SHOW INDEX FROM servers;
```

## 🎉 완료된 기능

✅ **MySQL 데이터베이스 연결**  
✅ **servers 테이블 생성 및 관리**  
✅ **서버 등록/수정/삭제 API**  
✅ **웹 인터페이스 연동**  
✅ **SSH 키 설치 시 자동 저장**  
✅ **서버 타입별 아이콘 표시**  
✅ **등록일/수정일 추적**  
✅ **중복 방지 (host, port, username)**  
✅ **연결 테스트 및 빠른 접속**  
✅ **한글 완전 지원 (UTF8MB4)**  

---

🎊 **축하합니다!** 이제 MySQL 기반의 강력한 서버 관리 시스템을 사용할 수 있습니다! 
