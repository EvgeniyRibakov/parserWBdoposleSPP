@echo off
echo ========================================
echo ЗАПУСК CHROME В DEBUG-РЕЖИМЕ
echo ========================================
echo.

REM Получаем полный путь к User Data
set USER_DATA=%LOCALAPPDATA%\Google\Chrome\User Data
echo Путь к профилю: %USER_DATA%
echo.

echo Закрываю все процессы Chrome...
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 >nul

echo Запускаю Chrome с debug-портом 9222...
echo.

REM Запускаем Chrome с полным путём (Profile 4 для парсера)
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USER_DATA%" --profile-directory="Profile 4"

echo.
echo ========================================
echo ✓ Chrome запущен!
echo ========================================
echo.
echo Подожди 3 секунды пока Chrome загрузится...
timeout /t 3 >nul

echo Проверяю порт 9222...
netstat -an | findstr "9222" >nul
if %errorlevel% == 0 (
    echo ✓ Порт 9222 открыт - всё готово!
) else (
    echo ✗ Порт 9222 не открыт - проверь что Chrome запустился
)

echo.
echo Теперь запусти: python Parser_WB_Search.py
echo (или установите USE_REMOTE_CHROME = True в коде)
echo.
pause

