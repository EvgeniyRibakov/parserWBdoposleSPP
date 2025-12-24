@echo off
chcp 65001 >nul
echo ================================================================================
echo УСТАНОВКА ЗАВИСИМОСТЕЙ ДЛЯ ПАРСЕРА WB MISSING
echo ================================================================================
echo.

echo [1/3] Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] ОШИБКА: Python не найден!
    echo.
    echo Установите Python с https://www.python.org/downloads/
    echo При установке отметьте галочку "Add Python to PATH"
    pause
    exit /b 1
)
python --version
echo ✓ Python найден
echo.

echo [2/3] Установка зависимостей...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [!] ОШИБКА при установке зависимостей!
    echo Попробуйте запустить вручную: pip install -r requirements.txt
    pause
    exit /b 1
)
echo ✓ Зависимости установлены
echo.

echo [3/3] Создание файла .env...
if not exist .env (
    copy .env_sample .env >nul 2>&1
    echo ✓ Файл .env создан из .env_sample
) else (
    echo ✓ Файл .env уже существует
)
echo.

echo ================================================================================
echo УСТАНОВКА ЗАВЕРШЕНА
echo ================================================================================
echo.
echo Теперь можно запустить парсер:
echo   python Parser_WB_Missing.py
echo.
pause


