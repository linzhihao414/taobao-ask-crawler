@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   淘宝问大家采集工具
echo ============================================
echo.
echo 关键词在"关键词.txt"里改
echo 结果会保存到"导出结果"文件夹
echo.
pause
E:\中沃皮革\小红书笔记\.venv\Scripts\python.exe taobao_ask_crawler.py
pause
