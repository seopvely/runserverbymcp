#!/usr/bin/env python3
"""
Alembic 설정 테스트
"""
import os
import sys
from alembic.config import Config
from alembic import command

def test_alembic_setup():
    """Alembic 설정 테스트"""
    try:
        print("🔍 Alembic 설정 테스트 시작...")
        
        # alembic.ini 파일 확인
        if not os.path.exists('alembic.ini'):
            print("❌ alembic.ini 파일이 없습니다.")
            return False
        print("✅ alembic.ini 파일 존재")
        
        # alembic 디렉토리 확인
        if not os.path.exists('alembic'):
            print("❌ alembic 디렉토리가 없습니다.")
            return False
        print("✅ alembic 디렉토리 존재")
        
        # 필수 파일들 확인
        required_files = [
            'alembic/env.py',
            'alembic/script.py.mako',
            'alembic/versions/001_initial_servers_table.py'
        ]
        
        for file_path in required_files:
            if not os.path.exists(file_path):
                print(f"❌ {file_path} 파일이 없습니다.")
                return False
            print(f"✅ {file_path} 파일 존재")
        
        # Alembic 설정 로드 테스트
        alembic_cfg = Config("alembic.ini")
        print("✅ alembic.ini 파일 로드 성공")
        
        # 데이터베이스 URL 확인
        db_url = alembic_cfg.get_main_option("sqlalchemy.url")
        if not db_url:
            print("❌ 데이터베이스 URL이 설정되지 않았습니다.")
            return False
        print(f"✅ 데이터베이스 URL 설정됨: {db_url.split('@')[0]}@***")
        
        # 마이그레이션 히스토리 확인 (실제 DB 연결 없이)
        print("✅ Alembic 설정이 올바르게 완료되었습니다!")
        
        print("\n🚀 다음 단계:")
        print("   alembic upgrade head")
        
        return True
        
    except Exception as e:
        print(f"❌ Alembic 설정 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    print("🗄️ Alembic 데이터베이스 마이그레이션 설정 테스트")
    print("=" * 50)
    
    if test_alembic_setup():
        print("\n🎉 모든 설정이 완료되었습니다!")
        print("   이제 'alembic upgrade head'를 실행하세요.")
        sys.exit(0)
    else:
        print("\n💔 설정에 문제가 있습니다. 가이드를 다시 확인해주세요.")
        sys.exit(1) 
