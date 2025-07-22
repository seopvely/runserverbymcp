#!/usr/bin/env python3
"""
MySQL 데이터베이스 연결 테스트
"""
import pymysql
import sys

# MySQL 연결 설정
MYSQL_CONFIG = {
    'host': '192.168.0.10',
    'user': 'runmcp',
    'password': 'rcpGsy2*dmQ',
    'database': 'runmcp',
    'charset': 'utf8mb4',
    'autocommit': True
}

def test_connection():
    """MySQL 연결 테스트"""
    try:
        print("🔍 MySQL 연결 테스트 시작...")
        print(f"   호스트: {MYSQL_CONFIG['host']}")
        print(f"   사용자: {MYSQL_CONFIG['user']}")
        print(f"   데이터베이스: {MYSQL_CONFIG['database']}")
        
        # 연결 테스트
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        
        # 버전 확인
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"✅ 연결 성공! MySQL 버전: {version[0]}")
        
        # 테이블 존재 확인
        cursor.execute("SHOW TABLES LIKE 'servers'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            print("✅ servers 테이블이 이미 존재합니다.")
            
            # 테이블 구조 확인
            cursor.execute("DESCRIBE servers")
            columns = cursor.fetchall()
            print("📊 테이블 구조:")
            for col in columns:
                print(f"   - {col[0]} {col[1]} {col[2]} {col[3]} {col[4]}")
        else:
            print("⚠️  servers 테이블이 존재하지 않습니다. 애플리케이션 시작 시 생성될 예정입니다.")
        
        conn.close()
        print("✅ MySQL 연결 테스트 완료!")
        return True
        
    except pymysql.Error as e:
        print(f"❌ MySQL 연결 실패: {e}")
        return False
    except Exception as e:
        print(f"💥 예상치 못한 오류: {e}")
        return False

def create_servers_table():
    """servers 테이블 생성"""
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        
        print("🔨 servers 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                id INT PRIMARY KEY AUTO_INCREMENT,
                title VARCHAR(255) NOT NULL,
                host VARCHAR(255) NOT NULL,
                port INT DEFAULT 22,
                username VARCHAR(100) DEFAULT 'root',
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_server (host, port, username)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        print("✅ servers 테이블 생성 완료!")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")
        return False

if __name__ == "__main__":
    print("🚀 MySQL 데이터베이스 설정 테스트")
    print("=" * 50)
    
    # 연결 테스트
    if test_connection():
        # 테이블 생성
        create_servers_table()
        print("\n🎉 모든 설정이 완료되었습니다!")
        print("   이제 애플리케이션을 시작할 수 있습니다.")
    else:
        print("\n💔 연결 실패! MySQL 서버 설정을 확인해주세요.")
        sys.exit(1) 
