#!/bin/bash
# 봇 실행 스크립트
cd "$(dirname "$0")/.."

echo "==================================="
echo "  aicokuma TikTok 자동화 봇 시작"
echo "==================================="

# .env 확인
if [ ! -f .env ]; then
    echo "❌ .env 파일이 없습니다."
    echo "   cp .env.example .env 후 내용을 채우세요."
    exit 1
fi

# 의존성 확인
if ! python -c "import playwright" 2>/dev/null; then
    echo "의존성 설치 중..."
    pip install -r requirements.txt
    playwright install chromium
fi

# 봇 실행
echo "봇 시작..."
python -m bot.main
