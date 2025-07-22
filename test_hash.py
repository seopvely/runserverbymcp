import hashlib

def hash_password(password: str) -> str:
    """비밀번호를 SHA256으로 해시화"""
    return hashlib.sha256(password.encode()).hexdigest()

# 테스트할 비밀번호들
passwords = {
    "admin": "admin",
    "kqwer718@K@": "kqwer718@K@",
    "secret123": "secret123",
    "admin123": "admin123"
}

print("비밀번호 해시 계산:")
print("-" * 80)
for name, password in passwords.items():
    hash_value = hash_password(password)
    print(f"{name:15} => {hash_value}")

print("\n\nPython 딕셔너리 형식:")
print("USERS = {")
print(f'    "admin": "{hash_password("kqwer718@K@")}",  # kqwer718@K@')
print(f'    "user": "{hash_password("secret123")}",   # secret123')
print(f'    "ssh": "{hash_password("admin123")}",    # admin123')
print("}")
