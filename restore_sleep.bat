@echo off
powercfg /change standby-timeout-ac 30
schtasks /delete /tn "FootballVideo_RestoreSleep" /f
