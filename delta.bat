@echo off
setlocal
cd /d "C:\Users\sekem\OneDrive\Desktop\Projects3\Delta"
call venv\Scripts\activate.bat
python main.py %*
endlocal
