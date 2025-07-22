# SSH Remote Command Executor - FastMCP 서버

SSH 마스터키를 사용하여 원격 서버에서 쉘 명령어를 실행하는 FastMCP 서버입니다.

## 주요 기능

- ✅ SSH 마스터키를 통한 원격 서버 접속
- ✅ 쉘 명령어 원격 실행 및 결과 반환
- ✅ 배치 명령어 실행 지원
- ✅ 타임아웃 설정 가능
- ✅ 상세한 실행 로그 기록
- ✅ RESTful API 제공

## 설치 및 설정

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. SSH 마스터키 설정
```bash
# SSH 키를 .ssh/h_web2 경로에 복사
cp /path/to/your/ssh_key .ssh/h_web2

# 권한 설정 (자동으로 설정되지만 수동으로도 가능)
chmod 600 .ssh/h_web2
```

### 3. 서버 실행
```bash
# FastMCP 서버 시작 (포트 8001)
python runmcp_ssh_executor.py
```

## API 엔드포인트

### 1. 서버 상태 확인
```
GET /
```

응답 예시:
```json
{
  "service": "SSH Remote Command Executor",
  "status": "running",
  "version": "1.0.0",
  "key_exists": true
}
```

### 2. 단일 명령어 실행
```
POST /execute
```

요청 본문:
```json
{
  "host": "192.168.1.100",
  "command": "ls -la /",
  "username": "root",
  "port": 22,
  "timeout": 30,
  "use_master_key": true
}
```

응답 예시:
```json
{
  "success": true,
  "stdout": "total 64\ndrwxr-xr-x  24 root root 4096 Jan 21 10:00 .\n...",
  "stderr": "",
  "exit_code": 0,
  "error": null,
  "host": "192.168.1.100",
  "command": "ls -la /"
}
```

### 3. 배치 명령어 실행
```
POST /execute-batch
```

요청 본문:
```json
[
  {
    "host": "192.168.1.100",
    "command": "hostname",
    "username": "root"
  },
  {
    "host": "192.168.1.101",
    "command": "uptime",
    "username": "root"
  }
]
```

### 4. 서버 목록 조회
```
GET /servers
```

## 테스트 클라이언트 사용법

### 기본 테스트 실행
```bash
python test_ssh_client.py
```

### 대화형 모드 사용
테스트 클라이언트 실행 후 대화형 모드에서:
```
SSH> 192.168.1.100 ls -la
SSH> localhost echo "Hello World"
SSH> status
SSH> servers
SSH> exit
```

## 보안 고려사항

1. **SSH 키 보안**
   - SSH 마스터키는 반드시 안전한 경로에 보관
   - 파일 권한은 600으로 설정 (읽기 전용)
   - 키 파일은 Git에 절대 커밋하지 않음

2. **네트워크 보안**
   - HTTPS 사용 권장 (프로덕션 환경)
   - 방화벽 설정으로 접근 제한
   - API 인증 추가 고려

3. **명령어 실행 보안**
   - 위험한 명령어 필터링 고려
   - 실행 권한 제한
   - 감사 로그 유지

## 로그 파일

- `runmcp_ssh.log`: 모든 SSH 명령어 실행 기록
- 로그 레벨: INFO (기본값)
- 실시간 콘솔 출력 지원

## 문제 해결

### SSH 키 파일을 찾을 수 없음
```bash
# 키 파일 경로 확인
ls -la .ssh/h_web2

# 키 파일 생성 (필요시)
ssh-keygen -t rsa -b 4096 -f .ssh/h_web2
```

### 연결 거부됨
- 대상 서버의 SSH 서비스 확인
- 방화벽 설정 확인
- SSH 포트 번호 확인 (기본값: 22)

### 인증 실패
- SSH 키가 대상 서버에 등록되었는지 확인
- 사용자명이 올바른지 확인
- 키 파일 권한이 600인지 확인

## 확장 가능성

1. **인증 추가**: JWT 토큰 기반 API 인증
2. **서버 그룹 관리**: 서버 그룹별 명령어 실행
3. **스케줄링**: 정기적인 명령어 실행
4. **모니터링**: 실시간 서버 상태 모니터링
5. **웹 UI**: 관리자 대시보드 추가

## 라이선스

MIT LICENSE 
