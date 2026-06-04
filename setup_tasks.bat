@echo off
echo Tao 4 task Football Video...

schtasks /create /tn "FootballVideo_0700" /tr "D:\claude\football-video-agent\run_daily.bat" /sc daily /st 07:00 /f /rl highest
schtasks /create /tn "FootballVideo_1130" /tr "D:\claude\football-video-agent\run_daily.bat" /sc daily /st 11:30 /f /rl highest
schtasks /create /tn "FootballVideo_1730" /tr "D:\claude\football-video-agent\run_daily.bat" /sc daily /st 17:30 /f /rl highest
schtasks /create /tn "FootballVideo_2000" /tr "D:\claude\football-video-agent\run_daily.bat" /sc daily /st 20:00 /f /rl highest

echo.
echo Ket qua:
schtasks /query /fo table | findstr FootballVideo

pause
