from fastapi import Request, FastAPI, HTTPException, Depends, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
import logging
import os
import sys
import secrets
import hashlib
import hmac
import base64
import json
import uuid
import pymysql
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 세션 관리를 위한 시크릿 키 설정
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-change-this-in-production")

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
# =============================================================================
# 자체 세션 관리 시스템 (외부 의존성 없음)
# =============================================================================

class SimpleSessionStore:
	"""메모리 기반 간단한 세션 저장소"""
	def __init__(self):
		self.sessions: Dict[str, Dict] = {}
		self.session_timeout = timedelta(hours=24)  # 24시간
	
	def create_session(self, user_data: Dict) -> str:
		"""새 세션 생성"""
		session_id = str(uuid.uuid4())
		self.sessions[session_id] = {
			**user_data,
			'created_at': datetime.now(),
			'last_accessed': datetime.now()
		}
		return session_id
	
	def get_session(self, session_id: str) -> Optional[Dict]:
		"""세션 데이터 조회"""
		if not session_id or session_id not in self.sessions:
			return None
			
		session_data = self.sessions[session_id]
		
		# 세션 만료 확인
		if datetime.now() - session_data['last_accessed'] > self.session_timeout:
			del self.sessions[session_id]
			return None
		
		# 마지막 접근 시간 업데이트
		session_data['last_accessed'] = datetime.now()
		return session_data
	
	def update_session(self, session_id: str, data: Dict) -> bool:
		"""세션 데이터 업데이트"""
		if session_id in self.sessions:
			self.sessions[session_id].update(data)
			self.sessions[session_id]['last_accessed'] = datetime.now()
			return True
		return False
	
	def delete_session(self, session_id: str) -> bool:
		"""세션 삭제"""
		if session_id in self.sessions:
			del self.sessions[session_id]
			return True
		return False
	
	def cleanup_expired_sessions(self):
		"""만료된 세션들 정리"""
		current_time = datetime.now()
		expired_sessions = [
			session_id for session_id, data in self.sessions.items()
			if current_time - data['last_accessed'] > self.session_timeout
		]
		for session_id in expired_sessions:
			del self.sessions[session_id]
		return len(expired_sessions)

# 글로벌 세션 저장소
session_store = SimpleSessionStore()

def sign_session_id(session_id: str) -> str:
	"""세션 ID에 HMAC 서명 추가"""
	signature = hmac.new(
		SECRET_KEY.encode(), 
		session_id.encode(), 
		hashlib.sha256
	).digest()
	signed_data = f"{session_id}:{base64.b64encode(signature).decode()}"
	return base64.b64encode(signed_data.encode()).decode()

def verify_session_id(signed_session_id: str) -> Optional[str]:
	"""서명된 세션 ID 검증"""
	try:
		decoded_data = base64.b64decode(signed_session_id.encode()).decode()
		session_id, signature_b64 = decoded_data.split(':', 1)
		signature = base64.b64decode(signature_b64.encode())
		
		expected_signature = hmac.new(
			SECRET_KEY.encode(),
			session_id.encode(),
			hashlib.sha256
		).digest()
		
		if hmac.compare_digest(signature, expected_signature):
			return session_id
		return None
	except Exception:
		return None

# 세션 헬퍼 클래스
class SessionHelper:
	"""요청별 세션 헬퍼"""
	def __init__(self, request: Request):
		self.request = request
		self._session_id = None
		self._session_data = None
		self._loaded = False
	
	def _load_session(self):
		"""세션 데이터 로드"""
		if self._loaded:
			return
			
		cookie_value = self.request.cookies.get("session_id")
		print(f"🍪 세션 로드 시도:")
		print(f"   쿠키 값: {cookie_value[:20] if cookie_value else 'None'}...")
		
		if cookie_value:
			session_id = verify_session_id(cookie_value)
			print(f"   검증된 세션 ID: {session_id[:8] if session_id else 'None'}...")
			
			if session_id:
				self._session_id = session_id
				self._session_data = session_store.get_session(session_id) or {}
				print(f"   세션 데이터: {self._session_data}")
			else:
				self._session_data = {}
				print("   ⚠️  세션 검증 실패!")
		else:
			self._session_data = {}
			print("   🆕 새 세션 생성 필요")
		
		self._loaded = True
	
	def get(self, key: str, default=None):
		"""세션에서 값 조회"""
		self._load_session()
		return self._session_data.get(key, default)
	
	def set(self, key: str, value):
		"""세션에 값 설정"""
		self._load_session()
		self._session_data[key] = value
		
		if not self._session_id:
			self._session_id = session_store.create_session(self._session_data)
			print(f"🆕 새 세션 생성: {self._session_id[:8]}...")
		else:
			session_store.update_session(self._session_id, {key: value})
			print(f"♻️  세션 업데이트: {self._session_id[:8]}... | {key}={value}")
	
	def clear(self):
		"""세션 초기화"""
		if self._session_id:
			session_store.delete_session(self._session_id)
		self._session_id = None
		self._session_data = {}
	
	def get_cookie_value(self) -> Optional[str]:
		"""쿠키에 저장할 서명된 세션 ID 반환"""
		if self._session_id:
			return sign_session_id(self._session_id)
		return None

# 요청에 세션 헬퍼 추가
def get_session(request: Request) -> SessionHelper:
	"""요청에서 세션 헬퍼 가져오기"""
	if not hasattr(request.state, 'session_helper'):
		request.state.session_helper = SessionHelper(request)
	return request.state.session_helper

SESSION_ENABLED = True
print("✅ 자체 세션 관리 시스템이 활성화되었습니다.")

# 사용자 인증 모델
class LoginRequest(BaseModel):
	username: str
	password: str
	remember_me: bool = False
	redirect_url: str = "/"

class LoginResponse(BaseModel):
	success: bool
	message: str
	redirect_url: Optional[str] = None

def hash_password(password: str) -> str:
	"""비밀번호를 SHA256으로 해시화"""
	return hashlib.sha256(password.encode()).hexdigest()


# =============================================================================
# 데이터베이스 설정 및 서버 관리
# =============================================================================

# MySQL 데이터베이스 설정
MYSQL_CONFIG = {
    'host': '192.168.0.10',
    'user': 'runmcp',
    'password': 'rcpGsy2*dmQ',
    'database': 'runmcp',
    'charset': 'utf8mb4',
    'autocommit': True
}

class ServerModel(BaseModel):
	"""서버 정보 모델"""
	id: Optional[int] = None
	title: str
	host: str
	port: int = 22
	username: str = "root"
	description: Optional[str] = None
	created_at: Optional[datetime] = None
	updated_at: Optional[datetime] = None

class ServerCreateRequest(BaseModel):
	"""서버 생성 요청 모델"""
	title: str
	host: str
	port: int = 22
	username: str = "root"
	password: str
	description: Optional[str] = None

def init_database():
	"""데이터베이스 초기화"""
	try:
		conn = pymysql.connect(**MYSQL_CONFIG)
		cursor = conn.cursor()
		
		# servers 테이블 생성
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
		
		conn.close()
		logger.info("MySQL 데이터베이스 초기화 완료")
		return True
	except Exception as e:
		logger.error(f"MySQL 데이터베이스 초기화 오류: {str(e)}")
		return False

def get_db_connection():
	"""데이터베이스 연결 반환"""
	conn = pymysql.connect(**MYSQL_CONFIG)
	return conn

def create_server(server_data: ServerCreateRequest) -> Optional[int]:
	"""서버 정보를 데이터베이스에 저장"""
	try:
		conn = get_db_connection()
		cursor = conn.cursor()
		
		cursor.execute("""
			INSERT INTO servers (title, host, port, username, description, updated_at)
			VALUES (%s, %s, %s, %s, %s, NOW())
			ON DUPLICATE KEY UPDATE 
			title = VALUES(title),
			description = VALUES(description),
			updated_at = NOW()
		""", (
			server_data.title,
			server_data.host,
			server_data.port,
			server_data.username,
			server_data.description
		))
		
		server_id = cursor.lastrowid
		conn.close()
		
		logger.info(f"서버 정보 저장 완료: {server_data.title} ({server_data.host})")
		return server_id
	except Exception as e:
		logger.error(f"서버 정보 저장 오류: {str(e)}")
		return None

def get_all_servers() -> List[Dict]:
	"""모든 서버 정보 조회"""
	try:
		conn = get_db_connection()
		cursor = conn.cursor(pymysql.cursors.DictCursor)  # Dictionary cursor 사용
		
		cursor.execute("""
			SELECT id, title, host, port, username, description, created_at, updated_at
			FROM servers
			ORDER BY created_at DESC
		""")
		
		servers = []
		for row in cursor.fetchall():
			servers.append({
				"id": row["id"],
				"title": row["title"],
				"host": row["host"],
				"port": row["port"],
				"username": row["username"],
				"description": row["description"],
				"created_at": row["created_at"].isoformat() if row["created_at"] else None,
				"updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
				"name": f"{row['username']}@{row['host']}"  # 호환성을 위해 name 필드 추가
			})
		
		conn.close()
		return servers
	except Exception as e:
		logger.error(f"서버 목록 조회 오류: {str(e)}")
		return []

def delete_server(server_id: int) -> bool:
	"""서버 정보 삭제"""
	try:
		conn = get_db_connection()
		cursor = conn.cursor()
		
		cursor.execute("DELETE FROM servers WHERE id = %s", (server_id,))
		
		deleted = cursor.rowcount > 0
		conn.close()
		
		if deleted:
			logger.info(f"서버 정보 삭제 완료: ID {server_id}")
		return deleted
	except Exception as e:
		logger.error(f"서버 정보 삭제 오류: {str(e)}")
		return False

# 앱 시작 시 데이터베이스 초기화
try:
    if init_database():
        logger.info("✅ MySQL 데이터베이스가 성공적으로 초기화되었습니다.")
    else:
        logger.warning("⚠️  데이터베이스 초기화에 실패했습니다. 일부 기능이 제한될 수 있습니다.")
except Exception as e:
    logger.error(f"💥 데이터베이스 초기화 중 심각한 오류: {str(e)}")
    logger.error("   MySQL 서버가 실행 중이고 연결 정보가 올바른지 확인해주세요.")
    logger.error(f"   연결 정보: {MYSQL_CONFIG['user']}@{MYSQL_CONFIG['host']}:{MYSQL_CONFIG.get('port', 3306)}/{MYSQL_CONFIG['database']}")

# 간단한 사용자 데이터 (실제 환경에서는 데이터베이스를 사용해야 함)
USERS = {
	"admin": hash_password("kqwer718@K@@"),  # kqwer718@K@@ (동적으로 계산)
	"user": "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f",   # secret123
	"ssh": "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918",    # admin123
}

def verify_password(plain_password: str, hashed_password: str) -> bool:
	"""비밀번호 검증"""
	computed_hash = hash_password(plain_password)
	print(f"🔑 비밀번호 검증: '{plain_password}' -> 계산된 해시: {computed_hash}")
	print(f"   저장된 해시: {hashed_password}")
	print(f"   검증 결과: {computed_hash == hashed_password}")
	return computed_hash == hashed_password

def get_current_user(request: Request) -> Optional[str]:
	"""현재 로그인된 사용자 정보 가져오기"""
	if not SESSION_ENABLED:
		return "admin"  # 세션이 비활성화된 경우 기본 사용자로 설정
	session = get_session(request)
	return session.get("user")

def require_auth(request: Request) -> str:
	"""인증이 필요한 엔드포인트에서 사용하는 의존성"""
	user = get_current_user(request)
	if not user:
		# 현재 URL을 redirect 파라미터로 포함하여 로그인 페이지로 리다이렉트
		redirect_url = f"/login?redirect={request.url.path}"
		if request.url.query:
			redirect_url += f"?{request.url.query}"
		raise HTTPException(status_code=401, detail=f"redirect:{redirect_url}")
	return user



@app.middleware("http")
async def auth_middleware(request: Request, call_next):
	# 인증이 필요하지 않은 경로들 (정확한 경로 매칭)
	public_paths = [
		"/login",
		"/auth/login",
		"/auth/logout", 
		"/auth/debug",
		"/static",
		"/favicon.ico"
	]
	
	# 현재 경로가 공개 경로인지 확인 (정확한 매칭 + startswith for static)
	is_public = (
		request.url.path in public_paths or 
		request.url.path.startswith("/static/") or
		request.url.path.startswith("/favicon") or
		request.url.path.startswith("/auth/debug")
	)
	

	# 중요한 요청만 로깅 (static 파일 제외)
	if not request.url.path.startswith("/static/") and not request.url.path.startswith("/favicon"):
		print(f"🔍 [{request.method}] {request.url.path}")
		print(f"   📋 Public paths: {public_paths}")
		print(f"   ✅ 공개 경로 여부: {is_public}")
		
		# 상세한 매칭 정보
		exact_match = request.url.path in public_paths
		static_match = request.url.path.startswith("/static/")
		favicon_match = request.url.path.startswith("/favicon")
		debug_match = request.url.path.startswith("/auth/debug")
		
		print(f"   🔍 매칭 상세:")
		print(f"      정확한 매칭: {exact_match}")
		print(f"      Static 매칭: {static_match}")
		print(f"      Favicon 매칭: {favicon_match}")
		print(f"      Debug 매칭: {debug_match}")
	
	# 인증이 필요한 경로이고 로그인하지 않은 경우 (세션이 활성화된 경우만)
	if SESSION_ENABLED and not is_public:
		session = get_session(request)
		current_user = session.get("user")
		
		if not current_user:
			if not request.url.path.startswith("/static/") and not request.url.path.startswith("/favicon"):
				print(f"   🚫 인증되지 않은 접근 시도")
			
		# API 요청인 경우 401 에러 반환
			content_type = request.headers.get("content-type", "")
			accept_header = request.headers.get("accept", "")
			
			# JSON/API 요청인지 확인
			is_api_request = (
				"application/json" in content_type or
				"application/json" in accept_header or
				request.url.path.startswith("/api/") or
				request.url.path.startswith("/auth/") or
				request.method in ["POST", "PUT", "DELETE", "PATCH"]
			)
			
			print(f"   📊 요청 분석:")
			print(f"      Content-Type: {content_type}")
			print(f"      Accept: {accept_header}")
			print(f"      Method: {request.method}")
			print(f"      Path: {request.url.path}")
			print(f"      API 요청 여부: {is_api_request}")
			
			# API 요청인 경우 JSON으로 401 응답
			if is_api_request:
				print("   🚫 API 요청 - JSON 401 응답")
				from fastapi.responses import JSONResponse
				return JSONResponse(
					status_code=401,
					content={
						"error": "Unauthorized",
						"message": "로그인이 필요합니다.",
						"redirect": "/login"
					}
				)
			
			# HTML 요청인 경우 로그인 페이지로 리다이렉트
			print("   🌐 HTML 요청 - 로그인 페이지로 리다이렉트")
			import urllib.parse
			
			# 원본 URL 구성 (쿼리 파라미터 포함)
			original_url = str(request.url.path)
			if request.url.query:
				original_url += f"?{request.url.query}"
			
			# URL 인코딩하여 redirect 파라미터로 전달
			encoded_url = urllib.parse.quote(original_url, safe='')
			redirect_url = f"/login?redirect={encoded_url}"
			
			print(f"   🔄 리다이렉트: {redirect_url}")
			return RedirectResponse(url=redirect_url, status_code=302)
	
	# 다음 미들웨어나 라우트 핸들러로 요청 전달
	response = await call_next(request)
	
	# 세션 쿠키 설정 (세션이 변경된 경우)
	if SESSION_ENABLED and hasattr(request.state, 'session_helper'):
		session_helper = request.state.session_helper
		cookie_value = session_helper.get_cookie_value()
		
		print(f"🍪 쿠키 설정 처리:")
		print(f"   경로: {request.url.path}")
		print(f"   쿠키 값: {cookie_value[:20] if cookie_value else 'None'}...")
		
		if cookie_value:
			response.set_cookie(
				"session_id",
				cookie_value,
				max_age=86400,  # 24시간
				httponly=True,
				samesite="lax"
			)
			print(f"   ✅ 쿠키 설정 완료!")
		elif session_helper.get("user") is None:
			# 로그아웃된 경우 쿠키 삭제
			response.delete_cookie("session_id")
			print(f"   🗑️  쿠키 삭제 완료!")
	
	return response

@app.get("/open_weather_mcp")
async def open_weather_mcp(request: Request):
	from langchain_mcp_adapters.client import MultiServerMCPClient
	from langgraph.prebuilt import create_react_agent
	from langchain_teddynote.messages import ainvoke_graph, astream_graph
	from langchain_anthropic import ChatAnthropic

	model = ChatAnthropic(
		model_name="claude-3-7-sonnet-latest", temperature=0, max_tokens=20000
	)

	async with MultiServerMCPClient(
		{
			"Retriever": {
				# 서버의 포트와 일치해야 합니다.(8005번 포트)
				"url": "http://localhost:8005/sse",
				"transport": "sse",
			}
		}
	) as client:
		print(client.get_tools())
		agent = create_react_agent(model, client.get_tools())
		answer = await astream_graph(agent, {"messages": "서울의 날씨는 어떠니?"})

@app.get('/figma_mcp')
async def framelink_figma_mcp(request: Request):
	from langchain_mcp_adapters.client import MultiServerMCPClient
	from langgraph.prebuilt import create_react_agent
	from langchain_teddynote.messages import ainvoke_graph, astream_graph
	from langchain_anthropic import ChatAnthropic
	
	model = ChatAnthropic(
		model_name="claude-3-7-sonnet-latest", temperature=0, max_tokens=20000
	)
	
	async with MultiServerMCPClient(
		{
			"Generating_Figma_Project_HTML_CSS_JS_Code": {
				"url": "http://localhost:8006/sse",
				"transport": "sse"
			}

		}
	) as client:
		print(client.get_tools())
		agent = create_react_agent(model, client.get_tools())
		answer = await astream_graph(agent, {"messages": "전달받은 링크에 관한 하이라이트된 디자인을 HTML, CSS, JS 코드로 변환해줘, 링크는 https://www.figma.com/design/jplrpLmarsbIp1dtdt0h4E/%ED%94%BD%EC%85%80%EC%97%90%EC%9D%B4%EB%B8%94?node-id=1-2&t=qrTCKj1Dw4KGQrZ6-4"})

@app.get('/show')
async def show(request: Request):
	return templates.TemplateResponse('show2.html', {'request': request})

@app.get('/ssh')
async def ssh_interface(request: Request):
	"""SSH 명령어 실행 웹 인터페이스"""
	return templates.TemplateResponse('show2.html', {'request': request})

@app.get('/ssh/status')
async def ssh_status():
	"""SSH Executor 서버 상태 확인"""
	import requests
	try:
		response = requests.get('https://runmcp.hankyeul.com/', timeout=30)  # 5초에서 30초로 늘림
		return {"status": "running", "response": response.json()}
	except requests.exceptions.Timeout:
		return {"status": "timeout", "message": "SSH Executor 서버 응답 시간 초과"}
	except requests.exceptions.ConnectionError:
		return {"status": "connection_error", "message": "SSH Executor 서버에 연결할 수 없습니다"}
	except Exception as e:
		return {"status": "error", "message": str(e)}

@app.get('/ssh/sessions')
async def ssh_sessions():
	"""활성 SSH 세션 목록 조회"""
	import requests
	try:
		response = requests.get('https://runmcp.hankyeul.com/sessions', timeout=30)  # 5초에서 30초로 늘림
		return response.json()
	except requests.exceptions.Timeout:
		return {"sessions": [], "error": "SSH Executor 서버 응답 시간 초과"}
	except requests.exceptions.ConnectionError:
		return {"sessions": [], "error": "SSH Executor 서버에 연결할 수 없습니다"}
	except Exception as e:
		return {"sessions": [], "error": str(e)}

@app.get('/ssh/session/{session_id}')
async def ssh_session_info(session_id: str):
	"""특정 SSH 세션 정보 조회"""
	import requests
	try:
		response = requests.get(f'https://runmcp.hankyeul.com/session/{session_id}', timeout=30)  # 5초에서 30초로 늘림
		logging.info(response.json())
		return response.json()
	except requests.exceptions.Timeout:
		return {"error": "SSH Executor 서버 응답 시간 초과"}
	except requests.exceptions.ConnectionError:
		return {"error": "SSH Executor 서버에 연결할 수 없습니다"}
	except Exception as e:
		return {"error": str(e)}

@app.get('/ssh/session/{session_id}/history')
async def ssh_session_history(session_id: str):
	"""특정 SSH 세션의 명령어 히스토리 조회"""
	import requests
	try:
		response = requests.get(f'https://runmcp.hankyeul.com/session/{session_id}', timeout=30)  # 5초에서 30초로 늘림
		session_info = response.json()
		return {"command_history": session_info.get("command_history", [])}
	except requests.exceptions.Timeout:
		return {"command_history": [], "error": "SSH Executor 서버 응답 시간 초과"}
	except requests.exceptions.ConnectionError:
		return {"command_history": [], "error": "SSH Executor 서버에 연결할 수 없습니다"}
	except Exception as e:
		return {"command_history": [], "error": str(e)}

@app.get('/ssh/servers')
async def get_servers():
	"""서버 목록 조회 (데이터베이스에서)"""
	try:
		servers = get_all_servers()
		return {"servers": servers, "source": "database"}
	except Exception as e:
		logger.error(f"서버 목록 조회 오류: {str(e)}")
		return {"servers": [], "error": f"데이터베이스 오류: {str(e)}"}

@app.post('/ssh/servers')
async def create_server_endpoint(server_data: ServerCreateRequest):
	"""서버 정보 생성"""
	try:
		server_id = create_server(server_data)
		if server_id:
			return {
				"success": True,
				"message": "서버 정보가 성공적으로 저장되었습니다",
				"server_id": server_id
			}
		else:
			return {
				"success": False,
				"message": "서버 정보 저장에 실패했습니다"
			}
	except Exception as e:
		logger.error(f"서버 생성 API 오류: {str(e)}")
		return {
			"success": False,
			"message": f"서버 생성 중 오류: {str(e)}"
		}

@app.delete('/ssh/servers/{server_id}')
async def delete_server_endpoint(server_id: int):
	"""서버 정보 삭제"""
	try:
		success = delete_server(server_id)
		if success:
			return {
				"success": True,
				"message": "서버 정보가 성공적으로 삭제되었습니다"
			}
		else:
			return {
				"success": False,
				"message": "서버를 찾을 수 없습니다"
			}
	except Exception as e:
		logger.error(f"서버 삭제 API 오류: {str(e)}")
		return {
			"success": False,
			"message": f"서버 삭제 중 오류: {str(e)}"
		}

# SSH 세션 관리 API 엔드포인트들
@app.post('/ssh/session/create')
async def create_ssh_session(request: Request):
	"""SSH 세션 생성"""
	import requests
	try:
		body = await request.json()
		response = requests.post('https://runmcp.hankyeul.com/session/create', json=body, timeout=10)  # 10초에서 30초로 늘림
		return response.json()
	except requests.exceptions.Timeout:
		return {"success": False, "error": "SSH Executor 서버 응답 시간 초과"}
	except requests.exceptions.ConnectionError:
		return {"success": False, "error": "SSH Executor 서버에 연결할 수 없습니다"}
	except Exception as e:
		return {"success": False, "error": str(e)}

@app.post('/ssh/session/{session_id}/execute')
async def execute_in_session(session_id: str, request: Request):
	"""세션에서 명령어 실행"""
	import requests
	try:
		body = await request.json()
		response = requests.post(f'https://runmcp.hankyeul.com/session/{session_id}/execute', json=body, timeout=30)  # 30초에서 60초로 늘림
		return response.json()
	except requests.exceptions.Timeout:
		return {"success": False, "error": "SSH Executor 서버 응답 시간 초과 - 명령어 실행이 60초를 초과했습니다"}
	except requests.exceptions.ConnectionError:
		return {"success": False, "error": "SSH Executor 서버에 연결할 수 없습니다"}
	except Exception as e:
		return {"success": False, "error": str(e)}

@app.delete('/ssh/session_delete/{session_id}')
async def delete_ssh_session(session_id: str):
	"""SSH 세션 삭제"""
	import requests
	try:
		response = requests.delete(f'https://runmcp.hankyeul.com/session/{session_id}', timeout=10)  # 10초에서 30초로 늘림
		return response.json()
	except requests.exceptions.Timeout:
		return {"success": False, "error": "SSH Executor 서버 응답 시간 초과"}
	except requests.exceptions.ConnectionError:
		return {"success": False, "error": "SSH Executor 서버에 연결할 수 없습니다"}
	except Exception as e:
		return {"success": False, "error": str(e)}

# 터미널 관련 API 엔드포인트들
@app.post('/ssh/session/{session_id}/shell/start')
async def start_interactive_shell(session_id: str, request: Request):
	"""대화형 쉘 시작"""
	import requests
	try:
		# 대화형 쉘 시작은 시간이 더 걸릴 수 있으므로 타임아웃을 60초로 늘림
		response = requests.post(f'https://runmcp.hankyeul.com/session/{session_id}/shell/start', timeout=60)
		return response.json()
	except requests.exceptions.Timeout:
		return {"success": False, "error": "대화형 쉘 시작 시간 초과 (60초) - SSH 서버나 네트워크 연결을 확인해주세요"}
	except requests.exceptions.ConnectionError:
		return {"success": False, "error": "SSH Executor 서버에 연결할 수 없습니다 - 서버가 실행 중인지 확인해주세요"}
	except Exception as e:
		return {"success": False, "error": f"대화형 쉘 시작 중 오류: {str(e)}"}

@app.post('/ssh/session/{session_id}/shell/command')
async def send_shell_command(session_id: str, request: Request):
	"""대화형 쉘에서 명령어 실행"""
	import requests
	try:
		body = await request.json()
		response = requests.post(f'https://runmcp.hankyeul.com/session/{session_id}/shell/command', json=body, timeout=30)  # 30초에서 60초로 늘림
		return response.json()
	except requests.exceptions.Timeout:
		return {"success": False, "error": "SSH Executor 서버 응답 시간 초과 - 쉘 명령어 실행이 60초를 초과했습니다"}
	except requests.exceptions.ConnectionError:
		return {"success": False, "error": "SSH Executor 서버에 연결할 수 없습니다"}
	except Exception as e:
		return {"success": False, "error": str(e)}

@app.post('/ssh/session/{session_id}/shell/stop')
async def stop_interactive_shell(session_id: str):
	"""대화형 쉘 종료"""
	import requests
	try:
		response = requests.post(f'https://runmcp.hankyeul.com/session/{session_id}/shell/stop', json={}, timeout=10)  # 10초에서 30초로 늘림
		return response.json()
	except requests.exceptions.Timeout:
		return {"success": False, "error": "SSH Executor 서버 응답 시간 초과"}
	except requests.exceptions.ConnectionError:
		return {"success": False, "error": "SSH Executor 서버에 연결할 수 없습니다"}
	except Exception as e:
		return {"success": False, "error": str(e)}

@app.get('/ssh/security/events')
async def get_security_events(limit: int = 50):
	"""보안 이벤트 조회"""
	import requests
	try:
		response = requests.get(f'https://runmcp.hankyeul.com/security/events?limit={limit}', timeout=30)
		return response.json()
	except requests.exceptions.Timeout:
		return {"events": [], "error": "SSH Executor 서버 응답 시간 초과"}
	except requests.exceptions.ConnectionError:
		return {"events": [], "error": "SSH Executor 서버에 연결할 수 없습니다"}
	except Exception as e:
		return {"events": [], "error": str(e)}

@app.get('/ssh/security/stats')
async def get_security_stats():
	"""보안 통계 조회"""
	import requests
	try:
		response = requests.get('https://runmcp.hankyeul.com/security/stats', timeout=30)
		return response.json()
	except requests.exceptions.Timeout:
		return {"stats": {"error": "SSH Executor 서버 응답 시간 초과"}}
	except requests.exceptions.ConnectionError:
		return {"stats": {"error": "SSH Executor 서버에 연결할 수 없습니다"}}
	except Exception as e:
		return {"stats": {"error": str(e)}}

@app.post('/ssh/security/test')
async def test_security_check():
	"""보안 검사 테스트"""
	import requests
	try:
		response = requests.post('https://runmcp.hankyeul.com/security/test', timeout=30)
		return response.json()
	except requests.exceptions.Timeout:
		return {"test_results": [], "error": "SSH Executor 서버 응답 시간 초과"}
	except requests.exceptions.ConnectionError:
		return {"test_results": [], "error": "SSH Executor 서버에 연결할 수 없습니다"}
	except Exception as e:
		return {"test_results": [], "error": str(e)}

@app.post('/ssh/key-setup')
async def ssh_key_setup(request: Request):
	"""SSH 키 설정 (원격 서버에 공개키 설치) 및 데이터베이스 저장"""
	import requests
	try:
		body = await request.json()
		
		# SSH Executor 서버에 키 설치 요청
		response = requests.post('https://runmcp.hankyeul.com/ssh-key-setup', json=body, timeout=60)
		result = response.json()
		
		# SSH 키 설치가 성공했을 경우 데이터베이스에 서버 정보 저장
		if result.get('success') and result.get('key_installed'):
			try:
				# 제목이 없으면 자동 생성
				title = body.get('title') or f"{body['username']}@{body['host']}:{body.get('port', 22)}"
				description = body.get('description') or f"SSH 키 설치됨 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
				
				server_data = ServerCreateRequest(
					title=title,
					host=body['host'],
					port=body.get('port', 22),
					username=body['username'],
					password="",  # 비밀번호는 저장하지 않음 (보안)
					description=description
				)
				
				server_id = create_server(server_data)
				if server_id:
					result['server_saved'] = True
					result['server_id'] = server_id
					result['message'] = f"SSH 키 설치 및 서버 정보 저장 완료 (ID: {server_id})"
					logger.info(f"SSH 키 설치 및 서버 저장 성공: {title}")
				else:
					result['server_saved'] = False
					result['message'] = f"SSH 키 설치는 성공했으나 서버 정보 저장 실패: {result.get('message', '')}"
					logger.warning(f"SSH 키 설치 성공 but DB 저장 실패: {title}")
					
			except Exception as db_error:
				logger.error(f"서버 정보 저장 중 오류: {str(db_error)}")
				result['server_saved'] = False
				result['message'] = f"SSH 키 설치는 성공했으나 서버 정보 저장 중 오류: {str(db_error)}"
		
		return result
		
	except requests.exceptions.Timeout:
		return {"success": False, "message": "SSH 키 설정 시간 초과 (60초) - 네트워크나 서버 상태를 확인해주세요", "key_installed": False}
	except requests.exceptions.ConnectionError:
		return {"success": False, "message": "SSH Executor 서버에 연결할 수 없습니다", "key_installed": False}
	except Exception as e:
		return {"success": False, "message": f"SSH 키 설정 중 오류: {str(e)}", "key_installed": False}

# =============================================================================
# 인증 관련 엔드포인트
# =============================================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
	"""로그인 페이지 표시"""
	return templates.TemplateResponse("login.html", {"request": request})

@app.post("/auth/login")
async def login(request: Request, response: Response, login_data: LoginRequest):
	"""사용자 로그인 처리"""
	try:
		if not SESSION_ENABLED:
			# 세션이 비활성화된 경우 모든 로그인 시도를 성공으로 처리
			return LoginResponse(
				success=True, 
				message="로그인에 성공했습니다. (세션 비활성화 모드)",
				redirect_url=login_data.redirect_url
			)
		
		username = login_data.username.strip()
		password = login_data.password
		
		# 사용자 인증 확인
		if username in USERS and verify_password(password, USERS[username]):
			# 세션에 사용자 정보 저장
			session = get_session(request)
			session.set("user", username)
			session.set("login_time", datetime.now().isoformat())
			
			if login_data.remember_me:
				session.set("remember_me", True)
			
			# 쿠키 직접 설정 (미들웨어 대신)
			cookie_value = session.get_cookie_value()
			if cookie_value:
				response.set_cookie(
					"session_id",
					cookie_value,
					max_age=86400,  # 24시간
					httponly=True,
					samesite="lax"
				)
				print(f"🍪 로그인 시 쿠키 설정: {cookie_value[:20]}...")
			
			logger.info(f"사용자 '{username}' 로그인 성공")
			
			# 개발용: 로그인에 성공한 비밀번호의 해시값 출력
			print(f"✅ 로그인 성공! '{username}' 계정")
			print(f"   비밀번호 '{password}' 해시: {hash_password(password)}")
			print(f"   세션 ID: {session._session_id[:8] if session._session_id else 'None'}...")
			
			return LoginResponse(
				success=True, 
				message="로그인에 성공했습니다.",
				redirect_url=login_data.redirect_url
			)
		else:
			logger.warning(f"사용자 '{username}' 로그인 실패")
			return LoginResponse(
				success=False, 
				message="사용자명 또는 비밀번호가 올바르지 않습니다."
			)
			
	except Exception as e:
		logger.error(f"로그인 처리 중 오류: {str(e)}")
		return LoginResponse(
			success=False, 
			message="서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
		)

@app.post("/auth/logout")
async def logout(request: Request, response: Response):
	"""사용자 로그아웃 처리"""
	try:
		if not SESSION_ENABLED:
			return {"success": True, "message": "로그아웃되었습니다. (세션 비활성화 모드)"}
		
		session = get_session(request)
		username = session.get("user")
		if username:
			logger.info(f"사용자 '{username}' 로그아웃")
		
		# 세션 초기화
		session.clear()
		
		# 쿠키 삭제
		response.delete_cookie("session_id")
		
		return {"success": True, "message": "로그아웃되었습니다."}
	except Exception as e:
		logger.error(f"로그아웃 처리 중 오류: {str(e)}")
		return {"success": False, "message": "로그아웃 처리 중 오류가 발생했습니다."}

@app.get("/auth/user")
async def get_current_user_info(request: Request):
	"""현재 로그인된 사용자 정보 반환"""
	user = get_current_user(request)
	if not user:
		raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
	
	if SESSION_ENABLED:
		session = get_session(request)
		login_time = session.get("login_time", datetime.now().isoformat())
	else:
		login_time = datetime.now().isoformat()
	
	return {
		"username": user,
		"login_time": login_time,
		"is_authenticated": True,
		"session_enabled": SESSION_ENABLED
	}

# =============================================================================
# 세션 관리 엔드포인트 (관리자용)
# =============================================================================

@app.get("/auth/sessions")
async def get_session_info(request: Request):
	"""현재 세션 저장소 상태 조회 (관리자용)"""
	user = get_current_user(request)
	if not user:
		raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
	
	# 만료된 세션 정리
	cleaned_count = session_store.cleanup_expired_sessions()
	
	return {
		"total_sessions": len(session_store.sessions),
		"cleaned_expired": cleaned_count,
		"session_timeout_hours": 24,
		"current_sessions": [
			{
				"session_id": sid[:8] + "...",  # 보안상 일부만 표시
				"user": data.get("user", "unknown"),
				"created_at": data.get("created_at", "").strftime("%Y-%m-%d %H:%M:%S") if data.get("created_at") else "",
				"last_accessed": data.get("last_accessed", "").strftime("%Y-%m-%d %H:%M:%S") if data.get("last_accessed") else ""
			}
			for sid, data in session_store.sessions.items()
		]
	}

@app.post("/auth/cleanup")
async def cleanup_expired_sessions(request: Request):
	"""만료된 세션 수동 정리 (관리자용)"""
	user = get_current_user(request)
	if not user:
		raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
	
	cleaned_count = session_store.cleanup_expired_sessions()
	return {
		"success": True,
		"message": f"만료된 세션 {cleaned_count}개가 정리되었습니다.",
		"remaining_sessions": len(session_store.sessions)
	}

# 루트 경로를 SSH 관리 페이지로 리다이렉트
@app.get("/")
async def root():
	"""루트 경로 접근 시 SSH 관리 페이지로 리다이렉트"""
	return RedirectResponse(url="/ssh", status_code=302)
