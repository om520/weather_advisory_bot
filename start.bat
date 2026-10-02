@echo off
echo Activating virtual environment...
call .\.venv\Scripts\activate.bat

echo Starting server...
python app.py

echo.
echo If the server crashed, the error is printed above.
pause
