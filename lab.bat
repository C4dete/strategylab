@echo off
rem Laboratorio de combinacoes: lab.bat lab_grades\exemplo.json   (ou: lab.bat --eixo reversoes=0,1,2 --nome teste)
set PYTHONPATH=%~dp0backend
python -X utf8 -m strategylab.lab %*
