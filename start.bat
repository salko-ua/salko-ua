@echo off

:: Проставлення кодування
echo ===========================================================
chcp 65001 > nul
echo Set encoding UTF-8. %date% %time%

:: Вімкнення локальних змінних середовища
setlocal enabledelayedexpansion

:: Проставлення змінних середовища, а саме кешу та віртуального середовища
for %%i in ("%~dp0.") do set "PROJECT_NAME=%%~ni"
set "UNC_PREFIX=\\fileserver\Chebaturochka"
set "PATH_TO_PROJECT=%~dp0"
set "check=!PATH_TO_PROJECT:~0,26!"
if /i "!check!"=="!UNC_PREFIX!" (
    set "REST=!PATH_TO_PROJECT:~26!"
    set "PATH_TO_PROJECT=D:!REST!"
)
set "VENV_PATH=C:/Users/%username%/.uv/%PROJECT_NAME%"
set "VIRTUAL_ENV=C:/Users/%username%/.uv/%PROJECT_NAME%"
set "UV_PROJECT_ENVIRONMENT=C:/Users/%username%/.uv/%PROJECT_NAME%"
set "UV_CACHE_DIR=C:/Users/%username%/.cache/%PROJECT_NAME%/.uv_cache"
set "RUFF_CACHE_DIR=C:/Users/%username%/.cache/%PROJECT_NAME%/.ruff_cache"

:: Налащтування та перевірки
:: ====================================================
:: Заборона запуску скрипта не з 45 серверу
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4 Address"') do (
    set "IPv4_Address=%%a"
)
if "%IPv4_Address%" neq " 10.100.1.45" (
    echo Current server is:%IPv4_Address% - access is denied.
    pause
    exit /b
) else (
    echo Current server is:%IPv4_Address% - proceed.
)

:: Переприєднання до мережевого диску D !OPTIONAL!
if not exist "d:\" (
    net use d: /delete
    net use d: \\fileserver\chebaturochka
    echo Drive D: connected to \\fileserver\chebaturochka
) else (
    echo Drive D: already connected.
)

:: Встановлення uv, якщо не встановлено (для користувачів)
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo Uv is not installed. Installing...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
) else (
    echo Uv already installed.
)
:: ====================================================

:: Робота з uv
:: ====================================================
:: Перехід на диск D
cd /d %PATH_TO_PROJECT%

:: Перевірка чи існує віртуальне середовище та створення, якщо його немає
if not exist %VENV_PATH% (
    uv venv %VENV_PATH%
)

:: Виклик віртуального середовища
call %VENV_PATH%/Scripts/activate

:: Синхронізація бібліотек
echo Sync dependencies...
uv sync

:: Запуск програми
echo Start program...
python today.py

:: Зупинка вкінці !OPTIONAL!
echo ===========================================================
endlocal
:: ====================================================
