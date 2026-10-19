@echo off
rem StrategyLab - inicia o servidor local e abre o navegador.
rem Requisitos: Python 3.11+ com as dependencias de backend\requirements.txt e Node (so na 1a vez, para compilar a interface).
setlocal
cd /d "%~dp0"
title StrategyLab

if not exist "frontend\dist\index.html" (
  echo Primeira execucao: compilando a interface...
  call npm --prefix frontend install || goto :erro
  call npm --prefix frontend run build || goto :erro
)

echo.
echo  StrategyLab em http://127.0.0.1:8765   (feche esta janela ou use encerrar.bat para parar)
echo  O BD padrao leva ~6 s para carregar; a tela avisa quando estiver pronto.
echo.

start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8765"
python -m uvicorn strategylab.main:create_app --factory --app-dir backend --host 127.0.0.1 --port 8765
goto :eof

:erro
echo.
echo Falha ao preparar a interface. Veja a mensagem acima.
pause
