#!/bin/bash

# SSH FastMCP 서버 시작 스크립트

echo "========================================"
echo "  SSH Remote Command Executor - FastMCP"
echo "========================================"
echo ""

# SSH 키 확인
if [ ! -f ".ssh/h_web2" ]; then
    echo "⚠️  경고: SSH 마스터키가 없습니다 (.ssh/h_web2)"
    echo "   키 파일을 복사한 후 다시 시도하세요."
    echo ""
    echo "   예시: cp /path/to/your/ssh_key .ssh/h_web2"
    echo ""
else
    echo "✅ SSH 마스터키 확인됨"
    chmod 600 .ssh/h_web2
fi

# 서버 설정 파일 확인
if [ -f "servers.json" ]; then
    echo "✅ 서버 설정 파일 확인됨"
else
    echo "ℹ️  서버 설정 파일이 없습니다 (servers.json)"
    echo "   기본 설정을 사용합니다."
fi

echo ""
echo "🚀 FastMCP 서버를 시작합니다..."
echo "   URL: http://localhost:8001"
echo "   문서: http://localhost:8001/docs"
echo ""
echo "종료하려면 Ctrl+C를 누르세요."
echo ""

# FastMCP 서버 실행
python runmcp_ssh_executor.py 
