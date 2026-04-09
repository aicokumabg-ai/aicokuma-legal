FROM python:3.11-slim

# 시스템 의존성
RUN apt-get update && apt-get install -y \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치
RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .

# 세션 디렉토리 생성
RUN mkdir -p /app/data/tiktok_session

# Xvfb (가상 디스플레이) + 봇 동시 실행
CMD ["sh", "-c", "Xvfb :99 -screen 0 1920x1080x24 & python -m bot.main"]
