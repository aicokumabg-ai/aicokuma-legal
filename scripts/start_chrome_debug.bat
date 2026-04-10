@echo off
REM Windows용 — Chrome을 디버그 모드로 실행
REM 이 파일을 더블클릭하면 기존 Chrome 프로필로 디버그 포트가 열립니다

start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --profile-directory=Default

echo Chrome이 디버그 모드로 시작되었습니다 (포트 9222)
echo TikTok에 로그인 후 봇을 실행하세요.
pause
