@echo off
cd /d "%~dp0"
echo ============================================
echo   Taobao Ask-Everyone Crawler
echo ============================================
echo.
if not exist ".venv" (
    echo [1/3] Creating venv...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo [2/3] Installing playwright...
    pip install playwright openpyxl -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo [3/3] Installing chromium...
    playwright install chromium
    echo.
    echo Setup complete! Run again to start.
    pause
    exit /b
)
call .venv\Scripts\activate.bat
python taobao_ask_crawler.py
pause