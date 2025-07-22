#!/usr/bin/env python3
"""MySQL 연결 테스트"""
import pymysql

MYSQL_CONFIG = {
    'host': '192.168.0.10',
    'user': 'runmcp',
    'password': 'rcpGsy2*dmQ',
    'database': 'runmcp',
    'charset': 'utf8mb4',
    'autocommit': True
}

try:
    conn = pymysql.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT VERSION()")
    version = cursor.fetchone()
    print(f"✅ MySQL 연결 성공! 버전: {version[0]}")
    conn.close()
except Exception as e:
    print(f"❌ MySQL 연결 실패: {e}") 
