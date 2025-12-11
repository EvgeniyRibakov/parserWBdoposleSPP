@echo off
echo ========================================
echo ЗАПУСК EDGE В DEBUG-РЕЖИМЕ
echo ========================================
echo.

REM Получаем полный путь к User Data
set USER_DATA=%LOCALAPPDATA%\Microsoft\Edge\User Data
echo Путь к профилю: %USER_DATA%
echo.

echo Закрываю все процессы Edge...
taskkill /F /IM msedge.exe >nul 2>&1
timeout /t 2 >nul

echo Запускаю Edge с debug-портом 9222...
echo.

REM Запускаем Edge с полным путём
start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir="%USER_DATA%" --profile-directory="Default"

echo.
echo ========================================
echo ✓ Edge запущен!
echo ========================================
echo.
echo Подожди 3 секунды пока Edge загрузится...
timeout /t 3 >nul

echo Проверяю порт 9222...
netstat -an | findstr "9222" >nul
if %errorlevel% == 0 (
    echo ✓ Порт 9222 открыт - всё готово!
) else (
    echo ✗ Порт 9222 не открыт - проверь что Edge запустился
)

echo.
echo Теперь запусти: python Parser_WB_Search.py
echo (или установите USE_REMOTE_CHROME = True в коде)
echo.
pause


