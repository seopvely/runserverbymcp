#!/usr/bin/env python3
"""
SSH Remote Command Executor - FastMCP Server
SSH 마스터키를 사용하여 원격 서버에서 명령어를 실행하는 FastMCP 서버
실제 SSH 세션 기반 지속 연결 지원
"""

import os
import subprocess
import shlex
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
import json
import sys
import uuid
import asyncio
import threading
import time
from datetime import datetime, timedelta
import paramiko

# FastMCP 서버 설정
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

# 로깅 설정
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
	handlers=[
		logging.FileHandler('runmcp_ssh.log'),
		logging.StreamHandler(sys.stdout)
	]
)
logger = logging.getLogger(__name__)

# SSH 키 경로 설정
SSH_KEY_PATH = Path(__file__).parent / ".ssh" / "h_web2"

# 세션 관리
class SSHSession:
	def __init__(self, session_id: str, host: str, port: int, username: str, timeout: int = 30):
		self.session_id = session_id
		self.host = host
		self.port = port
		self.username = username
		self.timeout = timeout
		self.ssh_client = None
		self.shell_channel = None  # 대화형 쉘 채널
		self.created_at = datetime.now()
		self.last_activity = datetime.now()
		self.command_history = []
		self.is_active = False
		self.is_connected = False
		self.shell_mode = False  # 대화형 쉘 모드
		self.current_prompt = ""  # 현재 프롬프트 상태
		
	def connect(self, key_path: Path) -> bool:
		"""SSH 연결 생성"""
		try:
			self.ssh_client = paramiko.SSHClient()
			self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			
			# SSH 키 파일 사용
			if key_path and key_path.exists():
				logger.info(f"SSH 키 파일 사용: {key_path}")
				self.ssh_client.connect(
					hostname=self.host,
					port=self.port,
					username=self.username,
					key_filename=str(key_path),
					timeout=self.timeout,
					banner_timeout=self.timeout
				)
			else:
				# 키 파일이 없으면 에이전트 사용
				logger.info("SSH 키 파일이 없어서 SSH 에이전트 사용")
				self.ssh_client.connect(
					hostname=self.host,
					port=self.port,
					username=self.username,
					timeout=self.timeout,
					banner_timeout=self.timeout
				)
			
			self.is_connected = True
			self.is_active = True
			self.update_activity()
			logger.info(f"SSH 연결 성공: {self.host}:{self.port}")
			return True
			
		except Exception as e:
			logger.error(f"SSH 연결 실패: {self.host}:{self.port} - {str(e)}")
			self.cleanup()
			return False
	
	def execute_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
		"""세션에서 명령어 실행"""
		if not self.is_connected or not self.ssh_client:
			return {
				"success": False,
				"stdout": None,
				"stderr": None,
				"exit_code": -1,
				"error": "SSH 세션이 연결되지 않았습니다"
			}
		
		try:
			self.update_activity()
			
			# 명령어 실행
			stdin, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
			
			# 결과 읽기
			stdout_data = stdout.read().decode('utf-8')
			stderr_data = stderr.read().decode('utf-8')
			exit_code = stdout.channel.recv_exit_status()
			
			result = {
				"success": exit_code == 0,
				"stdout": stdout_data,
				"stderr": stderr_data,
				"exit_code": exit_code,
				"error": None
			}
			
			# 히스토리에 추가
			self.add_command(command, result)
			
			logger.info(f"명령어 실행 완료: {command} (exit_code: {exit_code})")
			return result
			
		except Exception as e:
			error_msg = f"명령어 실행 오류: {str(e)}"
			logger.error(error_msg)
			result = {
				"success": False,
				"stdout": None,
				"stderr": None,
				"exit_code": -1,
				"error": error_msg
			}
			self.add_command(command, result)
			return result
	
	def update_activity(self):
		"""세션 활동 시간 업데이트"""
		self.last_activity = datetime.now()
		
	def add_command(self, command: str, result: Dict[str, Any]):
		"""명령어 히스토리에 추가 (exec_command용)"""
		self.command_history.append({
			'command': command,
			'timestamp': datetime.now().isoformat(),
			'result': result,
			'type': 'exec'
		})
		# 히스토리 최대 100개 유지
		if len(self.command_history) > 100:
			self.command_history.pop(0)
	
	def is_expired(self, max_idle_time: int = 3600) -> bool:
		"""세션이 만료되었는지 확인 (기본 1시간)"""
		return (datetime.now() - self.last_activity).total_seconds() > max_idle_time
	
	def cleanup(self):
		"""세션 정리"""
		try:
			if self.shell_channel:
				self.shell_channel.close()
			if self.ssh_client:
				self.ssh_client.close()
		except Exception as e:
			logger.error(f"SSH 클라이언트 정리 오류: {str(e)}")
		finally:
			self.shell_channel = None
			self.ssh_client = None
			self.is_connected = False
			self.is_active = False
			self.shell_mode = False

	
	def start_interactive_shell(self) -> Dict[str, Any]:
		if not self.is_connected or not self.ssh_client:
			return {
				"success": False,
				"error": "SSH 세션이 연결되지 않았습니다"
			}
		
		try:
			if self.shell_channel:
				# 이미 쉘이 있으면 종료
				self.shell_channel.close()
			
			# 대화형 쉘 시작
			self.shell_channel = self.ssh_client.invoke_shell(
				term='xterm-256color',
				width=120,
				height=40
			)
			
			# 논블로킹 모드로 설정
			self.shell_channel.settimeout(0.1)
			
			# 초기 프롬프트 읽기
			time.sleep(0.5)  # 쉘 초기화 대기
			initial_output = self._read_shell_output()
			
			self.shell_mode = True
			self.current_prompt = self._extract_prompt(initial_output)
			self.update_activity()
			
			logger.info(f"대화형 쉘 시작: {self.session_id}")
			
			return {
				"success": True,
				"output": initial_output,
				"prompt": self.current_prompt
			}
			
		except Exception as e:
			error_msg = f"대화형 쉘 시작 오류: {str(e)}"
			logger.error(error_msg)
			return {
				"success": False,
				"error": error_msg
			}
	
	def send_shell_command(self, command: str) -> Dict[str, Any]:
		"""대화형 쉘에서 명령어 실행"""
		if not self.shell_mode or not self.shell_channel:
			return {
				"success": False,
				"output": "",
				"error": "대화형 쉘이 시작되지 않았습니다"
			}
		
		try:
			self.update_activity()
			
			# 명령어 전송
			self.shell_channel.send(command + '\n')
			
			# 출력 읽기 (약간의 대기 시간 후)
			time.sleep(0.3)
			output = self._read_shell_output()
			
			# 프롬프트 추출
			new_prompt = self._extract_prompt(output)
			if new_prompt:
				self.current_prompt = new_prompt
			
			# 히스토리에 추가
			result = {
				"success": True,
				"output": output,
				"prompt": self.current_prompt
			}
			
			self.add_shell_command(command, result)
			
			logger.info(f"쉘 명령어 실행: {command}")
			return result
			
		except Exception as e:
			error_msg = f"쉘 명령어 실행 오류: {str(e)}"
			logger.error(error_msg)
			result = {
				"success": False,
				"output": "",
				"error": error_msg
			}
			self.add_shell_command(command, result)
			return result
	
	def _read_shell_output(self, max_wait: float = 2.0) -> str:
		"""쉘 출력 읽기"""
		output = ""
		start_time = time.time()
		
		while time.time() - start_time < max_wait:
			try:
				if self.shell_channel.recv_ready():
					chunk = self.shell_channel.recv(4096).decode('utf-8', errors='ignore')
					output += chunk
					if chunk:
						start_time = time.time()  # 새로운 데이터가 오면 시간 리셋
				else:
					time.sleep(0.1)
			except Exception:
				break
		
		return output
	
	def _extract_prompt(self, output: str) -> str:
		"""출력에서 프롬프트 추출"""
		if not output:
			return self.current_prompt
		
		lines = output.strip().split('\n')
		if lines:
			# 마지막 줄이 프롬프트일 가능성이 높음
			last_line = lines[-1].strip()
			if last_line and ('$' in last_line or '#' in last_line or '>' in last_line):
				return last_line
		
		return self.current_prompt
	
	def stop_interactive_shell(self) -> bool:
		"""대화형 쉘 종료"""
		try:
			if self.shell_channel:
				self.shell_channel.close()
				self.shell_channel = None
			
			self.shell_mode = False
			self.current_prompt = ""
			logger.info(f"대화형 쉘 종료: {self.session_id}")
			return True
			
		except Exception as e:
			logger.error(f"대화형 쉘 종료 오류: {str(e)}")
			return False
	
	def add_shell_command(self, command: str, result: Dict[str, Any]):
		"""쉘 명령어 히스토리에 추가"""
		self.command_history.append({
			'command': command,
			'timestamp': datetime.now().isoformat(),
			'result': result,
			'type': 'shell'
		})
		# 히스토리 최대 100개 유지
		if len(self.command_history) > 100:
			self.command_history.pop(0)

# 요청 모델 정의
class SSHCommandRequest(BaseModel):
	"""SSH 명령어 실행 요청 모델"""
	host: str = Field(..., description="접속할 원격 서버 호스트 (IP 또는 도메인)")
	port: int = Field(22, description="SSH 포트 번호")
	username: str = Field("root", description="SSH 사용자명")
	command: str = Field(..., description="실행할 쉘 명령어")
	timeout: int = Field(30, description="명령어 실행 타임아웃 (초)")
	use_master_key: bool = Field(True, description="마스터키 사용 여부")

class SSHCommandResponse(BaseModel):
	"""SSH 명령어 실행 응답 모델"""
	success: bool
	stdout: Optional[str] = None
	stderr: Optional[str] = None
	exit_code: Optional[int] = None
	error: Optional[str] = None
	host: str
	command: str

class SSHSessionRequest(BaseModel):
	"""SSH 세션 생성 요청 모델"""
	host: str = Field(..., description="접속할 원격 서버 호스트")
	port: int = Field(22, description="SSH 포트 번호")
	username: str = Field("root", description="SSH 사용자명")
	timeout: int = Field(30, description="세션 타임아웃 (초)")
	use_master_key: bool = Field(True, description="마스터키 사용 여부")

class SSHSessionResponse(BaseModel):
	"""SSH 세션 생성 응답 모델"""
	session_id: str
	host: str
	username: str
	success: bool
	message: str

class SSHCommandInSessionRequest(BaseModel):
	"""세션 내 명령어 실행 요청 모델"""
	command: str = Field(..., description="실행할 명령어")
	timeout: int = Field(30, description="명령어 실행 타임아웃 (초)")

class SSHCommandInSessionResponse(BaseModel):
	"""세션 내 명령어 실행 응답 모델"""
	session_id: str
	success: bool
	stdout: Optional[str] = None
	stderr: Optional[str] = None
	exit_code: Optional[int] = None
	error: Optional[str] = None
	command: str

class SSHSessionInfoResponse(BaseModel):
	"""SSH 세션 정보 응답 모델"""
	session_id: str
	host: str
	username: str
	created_at: str
	last_activity: str
	is_active: bool
	is_connected: bool
	command_count: int
	command_history: List[Dict[str, Any]] = []

class ShellStartRequest(BaseModel):
	"""대화형 쉘 시작 요청 모델"""
	pass

class ShellCommandRequest(BaseModel):
	"""쉘 명령어 실행 요청 모델"""
	command: str = Field(..., description="실행할 쉘 명령어")

class ShellCommandResponse(BaseModel):
	"""쉘 명령어 실행 응답 모델"""
	session_id: str
	success: bool
	output: Optional[str] = None
	prompt: Optional[str] = None
	error: Optional[str] = None
	command: str

# SSH 실행 클래스
class SSHExecutor:
	def __init__(self, key_path: Path):
		self.key_path = key_path
		self.sessions: Dict[str, SSHSession] = {}
		self._validate_key()
		self._start_session_cleanup_thread()
	
	def _validate_key(self):
		"""SSH 키 파일 유효성 검사"""
		if not self.key_path.exists():
			logger.warning(f"SSH 키 파일이 존재하지 않습니다: {self.key_path}")
		else:
			# SSH 키 파일 권한 설정 (600)
			os.chmod(self.key_path, 0o600)
			logger.info(f"SSH 키 파일 권한 설정 완료: {self.key_path}")
	
	def _start_session_cleanup_thread(self):
		"""세션 정리 스레드 시작"""
		def cleanup_sessions():
			while True:
				try:
					expired_sessions = []
					for session_id, session in self.sessions.items():
						if session.is_expired():
							expired_sessions.append(session_id)
					
					for session_id in expired_sessions:
						self.close_session(session_id)
						logger.info(f"만료된 세션 정리: {session_id}")
					
					time.sleep(300)  # 5분마다 체크
				except Exception as e:
					logger.error(f"세션 정리 중 오류: {str(e)}")
					time.sleep(60)
		
		cleanup_thread = threading.Thread(target=cleanup_sessions, daemon=True)
		cleanup_thread.start()
	
	def create_session(self, host: str, port: int, username: str, timeout: int = 30, use_master_key: bool = True) -> str:
		"""SSH 세션 생성"""
		session_id = str(uuid.uuid4())
		
		try:
			session = SSHSession(session_id, host, port, username, timeout)
			
			# SSH 연결 생성
			key_path = self.key_path if use_master_key else None
			if session.connect(key_path):
				self.sessions[session_id] = session
				logger.info(f"SSH 세션 생성 성공: {session_id} - {host}")
				return session_id
			else:
				raise Exception("SSH 연결 생성 실패")
				
		except Exception as e:
			logger.error(f"SSH 세션 생성 실패: {host} - {str(e)}")
			raise e
	
	def close_session(self, session_id: str) -> bool:
		"""SSH 세션 종료"""
		if session_id in self.sessions:
			session = self.sessions[session_id]
			session.cleanup()
			del self.sessions[session_id]
			logger.info(f"SSH 세션 종료: {session_id}")
			return True
		return False
	
	def execute_in_session(self, session_id: str, command: str, timeout: int = 30) -> Dict[str, Any]:
		"""세션 내에서 명령어 실행"""
		if session_id not in self.sessions:
			return {
				"success": False,
				"stdout": None,
				"stderr": None,
				"exit_code": -1,
				"error": "세션이 존재하지 않습니다"
			}
		
		session = self.sessions[session_id]
		return session.execute_command(command, timeout)
	
	def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
		"""세션 정보 조회"""
		if session_id not in self.sessions:
			return None
		
		session = self.sessions[session_id]
		return {
			"session_id": session.session_id,
			"host": session.host,
			"username": session.username,
			"created_at": session.created_at.isoformat(),
			"last_activity": session.last_activity.isoformat(),
			"is_active": session.is_active,
			"is_connected": session.is_connected,
			"command_count": len(session.command_history),
			"command_history": session.command_history
		}
	
	def list_sessions(self) -> List[Dict[str, Any]]:
		"""활성 세션 목록 조회"""
		sessions_info = []
		for session_id, session in self.sessions.items():
			sessions_info.append({
				"session_id": session_id,
				"host": session.host,
				"username": session.username,
				"created_at": session.created_at.isoformat(),
				"last_activity": session.last_activity.isoformat(),
				"is_active": session.is_active,
				"is_connected": session.is_connected,
				"command_count": len(session.command_history)
			})
		return sessions_info

	def execute_remote_command(
		self,
		host: str,
		command: str,
		port: int = 22,
		username: str = "root",
		timeout: int = 30,
		use_master_key: bool = True
	) -> Dict[str, Any]:
		"""
		원격 서버에서 명령어 실행 (단일 실행용)
		"""
		try:
			# SSH 명령어 구성
			ssh_cmd = ["ssh"]
			
			# SSH 옵션 추가
			ssh_options = [
				"-o", "StrictHostKeyChecking=no",
				"-o", "UserKnownHostsFile=/dev/null",
				"-o", f"ConnectTimeout={timeout}",
				"-p", str(port),
			]
			
			# 마스터키 사용 시
			if use_master_key and self.key_path.exists():
				ssh_options.extend(["-i", str(self.key_path)])
			
			ssh_cmd.extend(ssh_options)
			
			# 사용자@호스트 추가
			ssh_cmd.append(f"{username}@{host}")
			
			# 실행할 명령어 추가
			ssh_cmd.append(command)
			
			logger.info(f"SSH 명령어 실행: {host} - {command}")
			
			# 명령어 실행
			result = subprocess.run(
				ssh_cmd,
				capture_output=True,
				text=True,
				timeout=timeout
			)
			
			return {
				"success": result.returncode == 0,
				"stdout": result.stdout,
				"stderr": result.stderr,
				"exit_code": result.returncode,
				"error": None
			}
			
		except subprocess.TimeoutExpired:
			error_msg = f"명령어 실행 타임아웃: {timeout}초"
			logger.error(error_msg)
			return {
				"success": False,
				"stdout": None,
				"stderr": None,
				"exit_code": -1,
				"error": error_msg
			}
		except Exception as e:
			error_msg = f"SSH 실행 오류: {str(e)}"
			logger.error(error_msg)
			return {
				"success": False,
				"stdout": None,
				"stderr": None,
				"exit_code": -1,
				"error": error_msg
			}

class InteractiveShell:
	def __init__(self, ssh_session):
		self.shell_channel = ssh_session.invoke_shell()
		self.buffer = ""
		
	def send_command(self, command):
		self.shell_channel.send(command + '\n')
		return self.read_output()
		
	def read_output(self):
		# 실시간 출력 읽기
		output = ""
		while self.shell_channel.recv_ready():
			chunk = self.shell_channel.recv(1024)
			output += chunk.decode('utf-8')
		return output

# FastMCP 앱 초기화
ssh_executor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
	"""앱 수명 주기 관리"""
	global ssh_executor
	logger.info("SSH Executor FastMCP 서버 시작")
	ssh_executor = SSHExecutor(SSH_KEY_PATH)
	yield
	logger.info("SSH Executor FastMCP 서버 종료")
	# 모든 세션 정리
	if ssh_executor:
		for session_id in list(ssh_executor.sessions.keys()):
			ssh_executor.close_session(session_id)

app = FastAPI(
	title="SSH Remote Command Executor",
	description="SSH 마스터키를 사용한 원격 명령어 실행 FastMCP 서버 (실제 세션 지원)",
	version="2.1.0",
	lifespan=lifespan
)

# 라우트 정의
@app.get("/")
async def root():
	"""서버 상태 확인"""
	return {
		"service": "SSH Remote Command Executor",
		"status": "running",
		"version": "2.1.0",
		"key_exists": SSH_KEY_PATH.exists(),
		"active_sessions": len(ssh_executor.sessions) if ssh_executor else 0
	}

@app.post("/execute", response_model=SSHCommandResponse)
async def execute_command(request: SSHCommandRequest):
	"""
	원격 서버에서 명령어 실행 (단일 실행)
	
	예제:
	```json
	{
		"host": "192.168.1.100",
		"command": "ls -la /",
		"username": "root",
		"port": 22,
		"timeout": 30
	}
	```
	"""
	if not ssh_executor:
		raise HTTPException(status_code=500, detail="SSH Executor가 초기화되지 않았습니다")
	
	# 명령어 실행
	result = ssh_executor.execute_remote_command(
		host=request.host,
		command=request.command,
		port=request.port,
		username=request.username,
		timeout=request.timeout,
		use_master_key=request.use_master_key
	)
	
	# 응답 생성
	response = SSHCommandResponse(
		success=result["success"],
		stdout=result["stdout"],
		stderr=result["stderr"],
		exit_code=result["exit_code"],
		error=result["error"],
		host=request.host,
		command=request.command
	)
	
	# 로그 기록
	if result["success"]:
		logger.info(f"명령어 실행 성공: {request.host} - {request.command}")
	else:
		logger.error(f"명령어 실행 실패: {request.host} - {request.command}")
	
	return response

@app.post("/session/create", response_model=SSHSessionResponse)
async def create_session(request: SSHSessionRequest):
	"""
	SSH 세션 생성
	
	예제:
	```json
	{
		"host": "192.168.1.100",
		"username": "root",
		"port": 22,
		"timeout": 30
	}
	```
	"""
	if not ssh_executor:
		raise HTTPException(status_code=500, detail="SSH Executor가 초기화되지 않았습니다")
	
	try:
		session_id = ssh_executor.create_session(
			host=request.host,
			port=request.port,
			username=request.username,
			timeout=request.timeout,
			use_master_key=request.use_master_key
		)
		
		return SSHSessionResponse(
			session_id=session_id,
			host=request.host,
			username=request.username,
			success=True,
			message="세션이 성공적으로 생성되었습니다"
		)
	except Exception as e:
		return SSHSessionResponse(
			session_id="",
			host=request.host,
			username=request.username,
			success=False,
			message=f"세션 생성 실패: {str(e)}"
		)

@app.post("/session/{session_id}/execute", response_model=SSHCommandInSessionResponse)
async def execute_in_session(session_id: str, request: SSHCommandInSessionRequest):
	"""
	세션 내에서 명령어 실행
	
	예제:
	```json
	{
		"command": "ls -la",
		"timeout": 30
	}
	```
	"""
	if not ssh_executor:
		raise HTTPException(status_code=500, detail="SSH Executor가 초기화되지 않았습니다")
	
	result = ssh_executor.execute_in_session(
		session_id=session_id,
		command=request.command,
		timeout=request.timeout
	)
	
	return SSHCommandInSessionResponse(
		session_id=session_id,
		success=result["success"],
		stdout=result["stdout"],
		stderr=result["stderr"],
		exit_code=result["exit_code"],
		error=result["error"],
		command=request.command
	)

@app.delete("/session_delete/{session_id}")
async def close_session(session_id: str):
	"""SSH 세션 종료"""
	if not ssh_executor:
		raise HTTPException(status_code=500, detail="SSH Executor가 초기화되지 않았습니다")
	
	success = ssh_executor.close_session(session_id)
	if success:
		return {"message": f"세션 {session_id}가 종료되었습니다"}
	else:
		raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")

@app.get("/session/{session_id}", response_model=SSHSessionInfoResponse)
async def get_session_info(session_id: str):
	"""세션 정보 조회"""
	if not ssh_executor:
		raise HTTPException(status_code=500, detail="SSH Executor가 초기화되지 않았습니다")
	
	session_info = ssh_executor.get_session_info(session_id)
	if session_info:
		return SSHSessionInfoResponse(**session_info)
	else:
		raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")

@app.get("/sessions")
async def list_sessions():
	"""활성 세션 목록 조회"""
	if not ssh_executor:
		raise HTTPException(status_code=500, detail="SSH Executor가 초기화되지 않았습니다")
	
	return {"sessions": ssh_executor.list_sessions()}

@app.post("/execute-batch")
async def execute_batch_commands(requests: List[SSHCommandRequest]):
	"""
	여러 서버에서 동시에 명령어 실행
	"""
	if not ssh_executor:
		raise HTTPException(status_code=500, detail="SSH Executor가 초기화되지 않았습니다")
	
	results = []
	for req in requests:
		result = ssh_executor.execute_remote_command(
			host=req.host,
			command=req.command,
			port=req.port,
			username=req.username,
			timeout=req.timeout,
			use_master_key=req.use_master_key
		)
		
		results.append(SSHCommandResponse(
			success=result["success"],
			stdout=result["stdout"],
			stderr=result["stderr"],
			exit_code=result["exit_code"],
			error=result["error"],
			host=req.host,
			command=req.command
		))
	
	return {"results": results, "total": len(results)}

@app.get("/servers")
async def list_servers():
	"""
	설정된 서버 목록 반환
	"""
	try:
		# servers.json 파일에서 서버 목록 읽기
		servers_file = Path(__file__).parent / "servers.json"
		if servers_file.exists():
			with open(servers_file, 'r', encoding='utf-8') as f:
				data = json.load(f)
				return {"servers": data.get("servers", []), "default_settings": data.get("default_settings", {})}
		else:
			# 파일이 없으면 기본 서버 목록 반환
			servers = [
				{"name": "localhost", "host": "localhost", "port": 22, "description": "로컬 서버"},
			]
			return {"servers": servers}
	except Exception as e:
		logger.error(f"서버 목록 로드 오류: {str(e)}")
		return {"servers": [], "error": str(e)}

@app.post("/session/{session_id}/shell/start")
async def start_interactive_shell_post(session_id: str):
	print("""대화형 쉘 시작""")
	if not ssh_executor:
		raise HTTPException(status_code=500, detail="SSH Executor가 초기화되지 않았습니다")
	
	if session_id not in ssh_executor.sessions:
		raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
	
	session = ssh_executor.sessions[session_id]
	
	result = session.start_interactive_shell()
	
	return result

@app.post("/session/{session_id}/shell/command", response_model=ShellCommandResponse)
async def send_shell_command(session_id: str, request: ShellCommandRequest):
	"""대화형 쉘에서 명령어 실행"""
	if not ssh_executor:
		raise HTTPException(status_code=500, detail="SSH Executor가 초기화되지 않았습니다")
	
	if session_id not in ssh_executor.sessions:
		raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
	
	session = ssh_executor.sessions[session_id]
	result = session.send_shell_command(request.command)
	
	return ShellCommandResponse(
		session_id=session_id,
		success=result["success"],
		output=result.get("output"),
		prompt=result.get("prompt"),
		error=result.get("error"),
		command=request.command
	)

@app.post("/session/{session_id}/shell/stop")
async def stop_interactive_shell(session_id: str):
	"""대화형 쉘 종료"""
	if not ssh_executor:
		raise HTTPException(status_code=500, detail="SSH Executor가 초기화되지 않았습니다")
	
	if session_id not in ssh_executor.sessions:
		raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
	
	session = ssh_executor.sessions[session_id]
	success = session.stop_interactive_shell()
	
	return {"success": success, "message": "대화형 쉘이 종료되었습니다" if success else "대화형 쉘 종료 실패"}

if __name__ == "__main__":
	# 서버 실행
	logger.info("SSH Remote Command Executor 시작")
	uvicorn.run(
		"runmcp_ssh_executor:app",
		host="0.0.0.0",
		port=8001,
		reload=True,
		log_level="info"
	) 
