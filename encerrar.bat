@echo off
rem StrategyLab - encerra o servidor que estiver escutando na porta 8765.
setlocal
set ACHOU=0
for /f "tokens=5" %%p in ('netstat -aon ^| findstr /R /C:":8765 .*LISTENING"') do (
  taskkill /PID %%p /F >nul 2>&1
  set ACHOU=1
)
if "%ACHOU%"=="1" (echo StrategyLab encerrado.) else (echo Nenhum StrategyLab rodando na porta 8765.)
