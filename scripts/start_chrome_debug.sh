#!/bin/bash
# Mac/Linux용 — Chrome을 디버그 모드로 실행

# 기존 Chrome 인스턴스 확인
if lsof -Pi :9222 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "✅ 이미 디버그 포트 9222가 열려 있습니다."
    exit 0
fi

# OS 감지
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Mac
    CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
elif command -v google-chrome &>/dev/null; then
    CHROME="google-chrome"
elif command -v chromium-browser &>/dev/null; then
    CHROME="chromium-browser"
else
    echo "Chrome을 찾을 수 없습니다."
    exit 1
fi

echo "Chrome 디버그 모드로 시작..."
"$CHROME" \
  --remote-debugging-port=9222 \
  --profile-directory=Default \
  &

echo "✅ Chrome이 시작되었습니다 (포트 9222)"
echo "TikTok(tiktok.com)에 로그인 후 봇을 실행하세요."
