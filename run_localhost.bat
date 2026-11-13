@echo off
chcp 65001 > nul
echo ============================================================
echo   KHỞI ĐỘNG HỆ THỐNG AI AGENT B2B SALES - CÔNG TY MINH AN
echo   Đang chạy trên máy chủ Localhost: http://localhost:8000
echo ============================================================
echo.

REM Kiểm tra uv hoặc python
where uv >nul 2>nul
if %errorlevel% equ 0 (
    uv run python server.py
    goto end
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    python server.py
    goto end
)

if exist "%USERPROFILE%\.local\bin\uv.exe" (
    "%USERPROFILE%\.local\bin\uv.exe" run python server.py
    goto end
)

if exist "%USERPROFILE%\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" (
    "%USERPROFILE%\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" server.py
    goto end
)

echo [LỖI] Không tìm thấy môi trường Python hoặc uv. Vui lòng kiểm tra lại.
pause

:end

