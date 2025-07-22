#!/usr/bin/env python3
"""
SSH FastMCP 서버 테스트 클라이언트
원격 명령어 실행 테스트를 위한 예제 스크립트
"""

import requests
import json
import sys
from typing import Optional

# FastMCP 서버 URL 설정
SERVER_URL = "http://localhost:8001"

def test_server_status():
    """서버 상태 확인"""
    try:
        response = requests.get(f"{SERVER_URL}/")
        if response.status_code == 200:
            data = response.json()
            print("=== 서버 상태 ===")
            print(f"서비스: {data['service']}")
            print(f"상태: {data['status']}")
            print(f"버전: {data['version']}")
            print(f"SSH 키 존재: {data['key_exists']}")
            print()
            return True
        else:
            print(f"서버 응답 오류: {response.status_code}")
            return False
    except Exception as e:
        print(f"서버 연결 실패: {str(e)}")
        return False

def execute_remote_command(
    host: str, 
    command: str, 
    username: str = "root",
    port: int = 22,
    timeout: int = 30
):
    """원격 명령어 실행"""
    try:
        # 요청 데이터 구성
        request_data = {
            "host": host,
            "command": command,
            "username": username,
            "port": port,
            "timeout": timeout,
            "use_master_key": True
        }
        
        print(f"\n=== 명령어 실행 ===")
        print(f"호스트: {host}")
        print(f"명령어: {command}")
        print(f"사용자: {username}")
        
        # API 호출
        response = requests.post(
            f"{SERVER_URL}/execute",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"\n실행 결과:")
            print(f"성공 여부: {result['success']}")
            print(f"종료 코드: {result['exit_code']}")
            
            if result['stdout']:
                print(f"\n표준 출력:")
                print(result['stdout'])
            
            if result['stderr']:
                print(f"\n표준 에러:")
                print(result['stderr'])
            
            if result['error']:
                print(f"\n오류:")
                print(result['error'])
                
            return result
        else:
            print(f"API 오류: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"요청 실패: {str(e)}")
        return None

def execute_batch_commands(commands_list):
    """여러 서버에서 배치 명령어 실행"""
    try:
        print("\n=== 배치 명령어 실행 ===")
        
        # API 호출
        response = requests.post(
            f"{SERVER_URL}/execute-batch",
            json=commands_list,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"총 {result['total']}개 명령어 실행")
            
            for idx, res in enumerate(result['results']):
                print(f"\n--- 명령어 {idx + 1} ---")
                print(f"호스트: {res['host']}")
                print(f"명령어: {res['command']}")
                print(f"성공: {res['success']}")
                if res['stdout']:
                    print(f"출력: {res['stdout'][:100]}...")  # 처음 100자만 표시
                    
            return result
        else:
            print(f"API 오류: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"배치 실행 실패: {str(e)}")
        return None

def list_servers():
    """서버 목록 조회"""
    try:
        response = requests.get(f"{SERVER_URL}/servers")
        if response.status_code == 200:
            data = response.json()
            print("\n=== 서버 목록 ===")
            for server in data['servers']:
                print(f"- {server['name']}: {server['host']}:{server['port']}")
            return data['servers']
        else:
            print(f"서버 목록 조회 실패: {response.status_code}")
            return []
    except Exception as e:
        print(f"서버 목록 조회 오류: {str(e)}")
        return []

def interactive_mode():
    """대화형 모드"""
    print("\n=== SSH FastMCP 대화형 모드 ===")
    print("명령어: exit (종료), status (상태), servers (서버목록)")
    print("형식: <호스트> <명령어>")
    print("예제: 192.168.1.100 ls -la\n")
    
    while True:
        try:
            user_input = input("SSH> ").strip()
            
            if user_input.lower() == 'exit':
                print("종료합니다.")
                break
            elif user_input.lower() == 'status':
                test_server_status()
            elif user_input.lower() == 'servers':
                list_servers()
            elif user_input:
                parts = user_input.split(maxsplit=1)
                if len(parts) >= 2:
                    host = parts[0]
                    command = parts[1]
                    execute_remote_command(host, command)
                else:
                    print("사용법: <호스트> <명령어>")
                    
        except KeyboardInterrupt:
            print("\n종료합니다.")
            break
        except Exception as e:
            print(f"오류: {str(e)}")

# 예제 실행
if __name__ == "__main__":
    # 서버 상태 확인
    if not test_server_status():
        print("서버가 실행중이지 않습니다.")
        print("먼저 'python runmcp_ssh_executor.py'로 서버를 시작하세요.")
        sys.exit(1)
    
    # 예제 1: 단일 명령어 실행
    print("\n### 예제 1: 단일 명령어 실행 ###")
    execute_remote_command("localhost", "echo 'Hello from SSH FastMCP'")
    
    # 예제 2: 서버 정보 조회
    print("\n### 예제 2: 서버 정보 조회 ###")
    execute_remote_command("localhost", "uname -a")
    
    # 예제 3: 디렉토리 목록
    print("\n### 예제 3: 디렉토리 목록 ###")
    execute_remote_command("localhost", "ls -la /tmp")
    
    # 예제 4: 배치 실행
    print("\n### 예제 4: 배치 실행 ###")
    batch_commands = [
        {
            "host": "localhost",
            "command": "hostname",
            "username": "root",
            "port": 22,
            "timeout": 10,
            "use_master_key": False  # 로컬 테스트용
        },
        {
            "host": "localhost", 
            "command": "uptime",
            "username": "root",
            "port": 22,
            "timeout": 10,
            "use_master_key": False
        }
    ]
    execute_batch_commands(batch_commands)
    
    # 대화형 모드 시작
    print("\n대화형 모드를 시작하려면 Enter를 누르세요...")
    input()
    interactive_mode() 
