@echo off
cd c:\Users\simon\PROJECTS\lyra_clean
start "Lyra Server" cmd /k "C:/Users/simon/PROJECTS/lyra_clean/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log"
timeout /t 3 /nobreak
C:/Users/simon/PROJECTS/lyra_clean/.venv/Scripts/python.exe scripts/test_api.py
pause
