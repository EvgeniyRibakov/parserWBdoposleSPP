# -*- coding: utf-8 -*-
"""
ПАРСЕР ЦЕН WILDBERRIES - ПРОСТОЙ ПАРСЕР ЦЕН
Открывает карточки товаров напрямую по артикулам и извлекает цену
Сохраняет результаты в текстовый файл: ссылка, артикул, цена

ИНСТРУКЦИЯ:
1. Сначала запустите: python Create_Links_Excel.py (создаст файл со ссылками)
2. Убедитесь что Chrome закрыт (или используйте remote режим)
3. Запустите: python Parser_WB_Search.py
4. Парсер читает ссылки из файла links_to_products.xlsx
5. Результаты сохраняются в prices_results.xlsx

РЕЖИМЫ РАБОТЫ:
- Обычный режим (USE_REMOTE_CHROME = False): запускает браузер с вашим профилем
- Remote режим (USE_REMOTE_CHROME = True): подключается к уже запущенному браузеру
  Для remote режима сначала запустите START_CHROME_DEBUG.bat

ВЫБОР БРАУЗЕРА:
- Chrome (BROWSER_TYPE = 'chrome') - по умолчанию
- Edge (BROWSER_TYPE = 'edge') - может работать стабильнее с профилями
"""

import os
import sys
import time
import random
import re
import subprocess
import shutil
from selenium import webdriver

# Настройка кодировки консоли для Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from openpyxl import load_workbook, Workbook
from selenium.common.exceptions import InvalidSessionIdException
import requests
import undetected_chromedriver as uc

# Конфигурация
# Пути относительно корня проекта
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

LINKS_EXCEL_FILE = os.path.join(DATA_DIR, "links_to_products.xlsx")
SHEET_LINKS = "Ссылки на товары"
OUTPUT_EXCEL_FILE = os.path.join(DATA_DIR, "prices_results.xlsx")

# Пути к Chrome
CHROME_USER_DATA_DIR = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
CHROME_PROFILE_NAME = "Default"  # ИЗМЕНЕНО: Profile 4 не запускается через Selenium, используем Default

# Пути к Edge
EDGE_USER_DATA_DIR = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
EDGE_PROFILE_NAME = "Default"  # "Default" для первого профиля (Пользователь 1), или "Profile 1", "Profile 2" и т.д.

# Использовать remote Chrome/Edge (если запущен через START_EDGE_DEBUG.bat или START_CHROME_DEBUG.bat)
USE_REMOTE_CHROME = False
CHROME_DEBUG_PORT = 9222

# Использовать временный профиль для парсинга (избегает конфликтов с запущенным Chrome)
USE_TEMP_PROFILE = True
TEMP_PROFILE_DIR = os.path.join(PROJECT_ROOT, "chrome_parser_profile")

# Копировать данные из Profile 4 в рабочий профиль
COPY_PROFILE_DATA = True
SOURCE_PROFILE_FOR_COPY = "Profile 4"  # Откуда копировать cookies

# Выбор браузера: 'chrome' или 'edge'
BROWSER_TYPE = 'chrome'  # 'chrome' или 'edge'

# Режим работы браузера
HEADLESS_MODE = False  # True = фоновый режим (без визуального окна), False = видимый браузер
# Примечание: В headless режиме нельзя авторизоваться вручную, используй готовый профиль!

# Пауза для ручной авторизации при первом запуске
WAIT_FOR_MANUAL_LOGIN = True  # Ждать пока пользователь авторизуется
MANUAL_LOGIN_TIMEOUT = 120  # Таймаут ожидания авторизации (секунды)

# Промежуточное сохранение результатов
SAVE_INTERMEDIATE_RESULTS = True  # Сохранять результаты каждые N товаров
SAVE_EVERY_N_PRODUCTS = 10  # Сохранять каждые 10 товаров (0 = только в конце)

# Параллельная обработка товаров
PARALLEL_TABS = 10  # Количество параллельных вкладок
DELAY_BETWEEN_BATCHES = (0.5, 1)  # Задержка между пакетами (мин, макс) в секундах
TEST_MODE = True  # True = тест на 50 товарах, False = все товары
TEST_PRODUCTS_COUNT = 50  # Количество товаров для тестирования


def check_chrome_running():
    """Проверяет, запущен ли Chrome"""
    try:
        print(f"[ЛОГ] Проверка запущенных процессов Chrome...")
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                              capture_output=True, text=True, timeout=5)
        is_running = 'chrome.exe' in result.stdout
        if is_running:
            print(f"[ЛОГ] Chrome процессы найдены:")
            # Подсчитываем количество процессов
            lines = [line for line in result.stdout.split('\n') if 'chrome.exe' in line]
            print(f"[ЛОГ]   Найдено процессов: {len(lines)}")
            for line in lines[:5]:  # Показываем первые 5
                print(f"[ЛОГ]   {line.strip()}")
        else:
            print(f"[ЛОГ] Chrome процессы не найдены")
        return is_running
    except Exception as e:
        print(f"[ЛОГ] Ошибка проверки Chrome процессов: {e}")
        return False


def check_edge_running():
    """Проверяет, запущен ли Edge"""
    try:
        print(f"[ЛОГ] Проверка запущенных процессов Edge...")
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq msedge.exe'], 
                              capture_output=True, text=True, timeout=5)
        is_running = 'msedge.exe' in result.stdout
        if is_running:
            print(f"[ЛОГ] Edge процессы найдены:")
            # Подсчитываем количество процессов
            lines = [line for line in result.stdout.split('\n') if 'msedge.exe' in line]
            print(f"[ЛОГ]   Найдено процессов: {len(lines)}")
            for line in lines[:5]:  # Показываем первые 5
                print(f"[ЛОГ]   {line.strip()}")
        else:
            print(f"[ЛОГ] Edge процессы не найдены")
        return is_running
    except Exception as e:
        print(f"[ЛОГ] Ошибка проверки Edge процессов: {e}")
        return False


def check_remote_chrome_available():
    """Проверяет, доступен ли Chrome в remote режиме"""
    try:
        import requests
        url = f"http://127.0.0.1:{CHROME_DEBUG_PORT}/json"
        print(f"[ЛОГ] Проверка remote Chrome: {url}")
        response = requests.get(url, timeout=2)
        print(f"[ЛОГ] Ответ: статус {response.status_code}")
        if response.status_code == 200:
            print(f"[ЛОГ] Remote Chrome доступен")
        return response.status_code == 200
    except Exception as e:
        print(f"[ЛОГ] Remote Chrome недоступен: {e}")
        return False


def copy_profile_data(source_profile, target_profile, copy_cookies=True, copy_storage=True):
    """
    Копирует данные из одного профиля Chrome в другой
    source_profile: путь к исходному профилю (Profile 4)
    target_profile: путь к целевому профилю
    """
    print(f"\n{'='*60}")
    print(f"[КОПИРОВАНИЕ] Перенос данных из Profile 4")
    print(f"{'='*60}")
    print(f"[ЛОГ] Источник: {source_profile}")
    print(f"[ЛОГ] Назначение: {target_profile}")
    
    if not os.path.exists(source_profile):
        print(f"[!] ОШИБКА: Исходный профиль не найден!")
        return False
    
    if not os.path.exists(target_profile):
        print(f"[ЛОГ] Создаю целевую директорию...")
        os.makedirs(target_profile, exist_ok=True)
    
    files_to_copy = []
    
    if copy_cookies:
        # Файлы с cookies и сессиями
        files_to_copy.extend([
            "Cookies",
            "Cookies-journal",
            "Network\\Cookies",
            "Network\\Cookies-journal",
            "Login Data",  # Сохраненные пароли и логины
            "Login Data-journal",
        ])
    
    if copy_storage:
        # Local Storage и другие данные
        files_to_copy.extend([
            "Local Storage",
            "Session Storage",
            "IndexedDB",
            "Preferences",  # Настройки профиля (ВАЖНО для адреса!)
            "Web Data",  # Автозаполнение форм (адреса, данные)
            "Web Data-journal",
            "History",  # История
            "History-journal",
        ])
    
    copied_count = 0
    for file_name in files_to_copy:
        source_file = os.path.join(source_profile, file_name)
        target_file = os.path.join(target_profile, file_name)
        
        if os.path.exists(source_file):
            try:
                # Создаём родительскую директорию если нужно
                target_dir = os.path.dirname(target_file)
                if target_dir and not os.path.exists(target_dir):
                    os.makedirs(target_dir, exist_ok=True)
                
                # Копируем файл или директорию
                if os.path.isdir(source_file):
                    if os.path.exists(target_file):
                        shutil.rmtree(target_file)
                    shutil.copytree(source_file, target_file)
                    print(f"[ЛОГ] ✓ Скопирована директория: {file_name}")
                else:
                    shutil.copy2(source_file, target_file)
                    file_size = os.path.getsize(source_file)
                    print(f"[ЛОГ] ✓ Скопирован файл: {file_name} ({file_size} байт)")
                
                copied_count += 1
            except Exception as e:
                print(f"[ЛОГ] ✗ Ошибка копирования {file_name}: {e}")
        else:
            print(f"[ЛОГ] - Файл не найден: {file_name}")
    
    print(f"\n[ЛОГ] Итого скопировано: {copied_count} элементов")
    print(f"{'='*60}\n")
    
    return copied_count > 0


def cleanup_profile_locks(profile_path):
    """Очищает lock-файлы профиля Chrome"""
    lock_files = [
        "SingletonLock",
        "lockfile",
        "SingletonSocket",
        "SingletonCookie"
    ]
    
    cleaned = False
    print(f"[ЛОГ] Очистка lock-файлов в: {profile_path}")
    
    for lock_file in lock_files:
        lock_path = os.path.join(profile_path, lock_file)
        if os.path.exists(lock_path):
            try:
                file_size = os.path.getsize(lock_path)
                print(f"[ЛОГ]   Удаляю: {lock_file} (размер: {file_size} байт)")
                os.remove(lock_path)
                cleaned = True
                print(f"[ЛОГ]   ✓ Удалено успешно")
            except Exception as e:
                print(f"[ЛОГ]   ✗ Ошибка удаления {lock_file}: {e}")
        else:
            print(f"[ЛОГ]   {lock_file} не найден")
    
    # Также очищаем DevToolsActivePort если есть
    devtools_port = os.path.join(profile_path, "DevToolsActivePort")
    if os.path.exists(devtools_port):
        try:
            file_size = os.path.getsize(devtools_port)
            print(f"[ЛОГ]   Удаляю: DevToolsActivePort (размер: {file_size} байт)")
            os.remove(devtools_port)
            cleaned = True
            print(f"[ЛОГ]   ✓ Удалено успешно")
        except Exception as e:
            print(f"[ЛОГ]   ✗ Ошибка удаления DevToolsActivePort: {e}")
    else:
        print(f"[ЛОГ]   DevToolsActivePort не найден")
    
    print(f"[ЛОГ] Результат очистки: {'очищено' if cleaned else 'нечего очищать'}")
    return cleaned


def setup_browser_driver():
    """
    Настраивает браузер (Chrome или Edge)
    Автоматически определяет режим работы
    """
    print(f"\n{'='*60}")
    print(f"[ДИАГНОСТИКА] Настройка браузера {BROWSER_TYPE.upper()}")
    print(f"{'='*60}")
    
    # Автоматическое определение режима
    auto_remote = False
    if not USE_REMOTE_CHROME:
        print(f"[ЛОГ] USE_REMOTE_CHROME = {USE_REMOTE_CHROME}")
        # Проверяем, доступен ли remote Chrome
        print(f"[ЛОГ] Проверка доступности remote Chrome на порту {CHROME_DEBUG_PORT}...")
        if check_remote_chrome_available():
            print(f"    [Авто] Обнаружен Chrome в remote режиме, переключаюсь...")
            auto_remote = True
        else:
            print(f"[ЛОГ] Remote Chrome недоступен")
    
    if USE_REMOTE_CHROME or auto_remote:
        # Подключение к уже запущенному браузеру
        print(f"[ЛОГ] Режим: Remote подключение")
        if BROWSER_TYPE == 'edge':
            options = EdgeOptions()
        else:
            options = ChromeOptions()
        
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{CHROME_DEBUG_PORT}")
        print(f"    [Режим] Подключение к {BROWSER_TYPE.upper()} (port {CHROME_DEBUG_PORT})")
        
        try:
            if BROWSER_TYPE == 'edge':
                driver = webdriver.Edge(options=options)
            else:
                driver = webdriver.Chrome(options=options)
            return driver
        except Exception as e:
            print(f"\n[!] ОШИБКА подключения к {BROWSER_TYPE.upper()}: {e}")
            print(f"\n💡 Убедись что браузер запущен через START_CHROME_DEBUG.bat")
            return None
    else:
        # Используем профиль пользователя
        print(f"[ЛОГ] Режим: Прямой запуск браузера")
        
        if BROWSER_TYPE == 'edge':
            # Edge использует другой путь к профилям
            profile_path = os.path.join(EDGE_USER_DATA_DIR, EDGE_PROFILE_NAME)
            options = EdgeOptions()
            
            print(f"[ЛОГ] Edge User Data Dir: {EDGE_USER_DATA_DIR}")
            print(f"[ЛОГ] Edge Profile Name: {EDGE_PROFILE_NAME}")
            print(f"[ЛОГ] Полный путь к профилю: {profile_path}")
            print(f"[ЛОГ] User Data Dir существует: {os.path.exists(EDGE_USER_DATA_DIR)}")
            print(f"[ЛОГ] Профиль существует: {os.path.exists(profile_path)}")
            
            # Проверяем, запущен ли Edge
            edge_running = check_edge_running()
            print(f"[ЛОГ] Edge запущен: {edge_running}")
            
            if edge_running:
                print(f"    ⚠ Edge уже запущен!")
                print(f"    [Авто] Пытаюсь очистить lock-файлы профиля...")
                
                # Автоматически очищаем lock-файлы
                cleaned = cleanup_profile_locks(profile_path)
                if cleaned:
                    print(f"    ✓ Lock-файлы очищены, пробую запустить...")
                    time.sleep(1)
                else:
                    print(f"    ⚠ Lock-файлы не найдены")
            else:
                # Очищаем старые lock-файлы на всякий случай
                print(f"[ЛОГ] Очистка lock-файлов профиля...")
                cleanup_profile_locks(profile_path)
            
            options.add_argument(f"--user-data-dir={EDGE_USER_DATA_DIR}")
            options.add_argument(f"--profile-directory={EDGE_PROFILE_NAME}")
            print(f"    [Режим] Запуск Edge с профилем '{EDGE_PROFILE_NAME}'")
        else:
            # Chrome
            profile_path = os.path.join(CHROME_USER_DATA_DIR, CHROME_PROFILE_NAME)
            options = ChromeOptions()
            
            print(f"[ЛОГ] Chrome User Data Dir: {CHROME_USER_DATA_DIR}")
            print(f"[ЛОГ] Chrome Profile Name: {CHROME_PROFILE_NAME}")
            print(f"[ЛОГ] Полный путь к профилю: {profile_path}")
            print(f"[ЛОГ] User Data Dir существует: {os.path.exists(CHROME_USER_DATA_DIR)}")
            print(f"[ЛОГ] Профиль существует: {os.path.exists(profile_path)}")
            
            # Проверяем наличие Chrome.exe
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe")
            ]
            chrome_found = False
            chrome_exe_path = None
            for path in chrome_paths:
                if os.path.exists(path):
                    chrome_found = True
                    chrome_exe_path = path
                    print(f"[ЛОГ] Chrome.exe найден: {path}")
                    break
            
            if not chrome_found:
                print(f"[ЛОГ] ⚠ Chrome.exe не найден в стандартных путях!")
                print(f"[ЛОГ] Проверенные пути:")
                for path in chrome_paths:
                    print(f"[ЛОГ]   - {path}")
            else:
                # НЕ устанавливаем binary_location - пусть Selenium найдет сам
                print(f"[ЛОГ] Chrome найден: {chrome_exe_path}")
            
            # Проверяем, запущен ли Chrome
            chrome_running = check_chrome_running()
            print(f"[ЛОГ] Chrome запущен (по tasklist): {chrome_running}")
            
            # Проверяем lock-файлы до очистки
            lock_files_before = []
            lock_files_to_check = ["SingletonLock", "lockfile", "SingletonSocket", "SingletonCookie", "DevToolsActivePort"]
            for lock_file in lock_files_to_check:
                lock_path = os.path.join(profile_path, lock_file)
                if os.path.exists(lock_path):
                    lock_files_before.append(lock_file)
                    print(f"[ЛОГ] Найден lock-файл: {lock_file} ({lock_path})")
            
            if chrome_running:
                print(f"    ⚠ Chrome уже запущен!")
                print(f"    [Авто] Пытаюсь очистить lock-файлы профиля...")
                
                # Автоматически очищаем lock-файлы
                cleaned = cleanup_profile_locks(profile_path)
                if cleaned:
                    print(f"    ✓ Lock-файлы очищены, пробую запустить...")
                    time.sleep(1)
                else:
                    print(f"    ⚠ Lock-файлы не найдены")
            else:
                # Очищаем старые lock-файлы на всякий случай
                print(f"[ЛОГ] Очистка lock-файлов профиля...")
                cleanup_profile_locks(profile_path)
            
            options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
            options.add_argument(f"--profile-directory={CHROME_PROFILE_NAME}")
            print(f"    [Режим] Запуск Chrome с профилем '{CHROME_PROFILE_NAME}'")
        
        # Дополнительные опции для стабильности
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--remote-debugging-port=9223")
        # КРИТИЧНО: отключаем расширения - они блокируют запуск через Selenium
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-popup-blocking")
        
        # Специальные опции для headless режима
        if HEADLESS_MODE:
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-renderer-backgrounding")
            print(f"[ЛОГ] Добавлены опции для headless режима")
        
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Логируем все аргументы
        print(f"[ЛОГ] Аргументы командной строки Chrome:")
        for arg in options.arguments:
            print(f"[ЛОГ]   - {arg}")
        
        # Логируем experimental options
        print(f"[ЛОГ] Experimental options:")
        for key, value in options.experimental_options.items():
            print(f"[ЛОГ]   - {key}: {value}")
        
        # Устанавливаем драйвер - ОДНА ПОПЫТКА
        print(f"\n[{BROWSER_TYPE.upper()}Driver] Установка/проверка драйвера...")
        print(f"[ЛОГ] Инициализация {BROWSER_TYPE}DriverManager...")
        
        try:
            if BROWSER_TYPE == 'edge':
                driver_path = EdgeChromiumDriverManager().install()
                print(f"[ЛОГ] EdgeDriver путь: {driver_path}")
                service = EdgeService(driver_path)
                print(f"[ЛОГ] Создание Edge WebDriver...")
                driver = webdriver.Edge(service=service, options=options)
            else:
                print(f"[ЛОГ] Используем UNDETECTED CHROMEDRIVER...")
                
                # Копируем данные из Profile 4 если нужно
                if COPY_PROFILE_DATA and USE_TEMP_PROFILE:
                    source_profile_path = os.path.join(CHROME_USER_DATA_DIR, SOURCE_PROFILE_FOR_COPY)
                    target_profile_path = TEMP_PROFILE_DIR
                    
                    print(f"[ЛОГ] Будет создан профиль парсера с данными из '{SOURCE_PROFILE_FOR_COPY}'")
                    
                    # Копируем данные из Profile 4
                    if os.path.exists(source_profile_path):
                        copy_profile_data(source_profile_path, target_profile_path)
                        # Очищаем lock-файлы в профиле парсера
                        print(f"[ЛОГ] Очистка lock-файлов в профиле парсера...")
                        cleanup_profile_locks(TEMP_PROFILE_DIR)
                        time.sleep(1)  # Небольшая задержка после копирования
                    else:
                        print(f"[!] Профиль '{SOURCE_PROFILE_FOR_COPY}' не найден, запускаю без копирования")
                
                if USE_TEMP_PROFILE:
                    mode_text = "headless (фоновый)" if HEADLESS_MODE else "видимый"
                    print(f"[ЛОГ] Запуск Chrome с профилем: {TEMP_PROFILE_DIR}...")
                    print(f"[ЛОГ] Режим: {mode_text}")
                    
                    # Для headless режима используем use_subprocess=True для стабильности
                    use_subprocess = HEADLESS_MODE
                    
                    # Проверяем, не мешают ли запущенные процессы Chrome
                    chrome_running = check_chrome_running()
                    if chrome_running and HEADLESS_MODE:
                        print(f"[ЛОГ] ⚠ Chrome уже запущен. Это может мешать headless режиму.")
                        print(f"[ЛОГ] Рекомендуется закрыть Chrome перед запуском парсера.")
                        print(f"[ЛОГ] Пробую запустить несмотря на это...")
                        time.sleep(2)  # Даем время на освобождение ресурсов
                    
                    # Пробуем несколько конфигураций для надежности
                    attempts = [
                        {'use_subprocess': use_subprocess, 'version_main': 143},
                        {'use_subprocess': True, 'version_main': 143},
                        {'use_subprocess': True, 'version_main': None},  # Автоопределение версии
                    ]
                    
                    driver = None
                    for attempt_num, attempt_config in enumerate(attempts, 1):
                        try:
                            print(f"[ЛОГ] Попытка {attempt_num}/{len(attempts)} запуска Chrome...")
                            print(f"[ЛОГ] Параметры: use_subprocess={attempt_config['use_subprocess']}, version_main={attempt_config['version_main']}")
                            
                            driver = uc.Chrome(
                                user_data_dir=TEMP_PROFILE_DIR,
                                headless=HEADLESS_MODE,
                                use_subprocess=attempt_config['use_subprocess'],
                                version_main=attempt_config['version_main']
                            )
                            
                            # Проверяем что драйвер работает
                            try:
                                driver.current_url  # Простая проверка работоспособности
                                print(f"[ЛОГ] ✓ Chrome запущен с профилем парсера (данные из Profile 4)")
                                break  # Успешно запустили, выходим из цикла
                            except Exception as check_error:
                                print(f"[ЛОГ] ⚠ Драйвер создан, но не отвечает: {check_error}")
                                try:
                                    driver.quit()
                                except:
                                    pass
                                driver = None
                                if attempt_num < len(attempts):
                                    print(f"[ЛОГ] Пробую следующую конфигурацию...")
                                    time.sleep(2)
                                    continue
                                else:
                                    raise Exception("Драйвер не отвечает после всех попыток")
                                    
                        except (ConnectionResetError, ConnectionError, ConnectionAbortedError) as conn_error:
                            error_msg = str(conn_error)
                            print(f"[ЛОГ] ✗ Попытка {attempt_num} не удалась: {type(conn_error).__name__}: {error_msg[:200]}")
                            
                            if attempt_num < len(attempts):
                                print(f"[ЛОГ] Ошибка подключения. Очищаю lock-файлы и пробую еще раз...")
                                cleanup_profile_locks(TEMP_PROFILE_DIR)
                                time.sleep(3)
                                continue
                            else:
                                raise
                                
                        except Exception as e:
                            error_msg = str(e)
                            print(f"[ЛОГ] ✗ Попытка {attempt_num} не удалась: {error_msg[:200]}")
                            
                            # Если ошибка связана с подключением, пробуем еще раз с задержкой
                            if any(keyword in error_msg.lower() for keyword in ["cannot connect", "not reachable", "connection", "reset", "refused"]):
                                if attempt_num < len(attempts):
                                    print(f"[ЛОГ] Ошибка подключения. Очищаю lock-файлы и пробую еще раз...")
                                    cleanup_profile_locks(TEMP_PROFILE_DIR)
                                    time.sleep(3)
                                    continue
                                else:
                                    raise
                            elif attempt_num < len(attempts):
                                print(f"[ЛОГ] Пробую следующую конфигурацию...")
                                time.sleep(2)
                                continue
                            else:
                                raise
                    
                    if driver is None:
                        raise Exception("Не удалось запустить Chrome после всех попыток")
                else:
                    mode_text = "headless (фоновый)" if HEADLESS_MODE else "видимый"
                    print(f"[ЛОГ] Запуск Chrome БЕЗ профиля (временный)...")
                    print(f"[ЛОГ] Режим: {mode_text}")
                    
                    # Пробуем несколько конфигураций для надежности
                    attempts_no_profile = [
                        {'use_subprocess': HEADLESS_MODE, 'version_main': 143},
                        {'use_subprocess': True, 'version_main': 143},
                        {'use_subprocess': True, 'version_main': None},  # Автоопределение версии
                    ]
                    
                    driver = None
                    for attempt_num, attempt_config in enumerate(attempts_no_profile, 1):
                        try:
                            print(f"[ЛОГ] Попытка {attempt_num}/{len(attempts_no_profile)} запуска Chrome...")
                            print(f"[ЛОГ] Параметры: use_subprocess={attempt_config['use_subprocess']}, version_main={attempt_config['version_main']}")
                            
                            driver = uc.Chrome(
                                headless=HEADLESS_MODE,
                                use_subprocess=attempt_config['use_subprocess'],
                                version_main=attempt_config['version_main']
                            )
                            
                            # Проверяем что драйвер работает
                            try:
                                driver.current_url  # Простая проверка работоспособности
                                print(f"[ЛОГ] ✓ Chrome запущен с временным профилем")
                                break  # Успешно запустили, выходим из цикла
                            except Exception as check_error:
                                print(f"[ЛОГ] ⚠ Драйвер создан, но не отвечает: {check_error}")
                                try:
                                    driver.quit()
                                except:
                                    pass
                                driver = None
                                if attempt_num < len(attempts_no_profile):
                                    print(f"[ЛОГ] Пробую следующую конфигурацию...")
                                    time.sleep(2)
                                    continue
                                else:
                                    raise Exception("Драйвер не отвечает после всех попыток")
                                    
                        except (ConnectionResetError, ConnectionError, ConnectionAbortedError) as conn_error:
                            error_msg = str(conn_error)
                            print(f"[ЛОГ] ✗ Попытка {attempt_num} не удалась: {type(conn_error).__name__}: {error_msg[:200]}")
                            
                            if attempt_num < len(attempts_no_profile):
                                print(f"[ЛОГ] Ошибка подключения. Пробую еще раз...")
                                time.sleep(3)
                                continue
                            else:
                                raise
                                
                        except Exception as e:
                            error_msg = str(e)
                            print(f"[ЛОГ] ✗ Попытка {attempt_num} не удалась: {error_msg[:200]}")
                            
                            # Если ошибка связана с подключением, пробуем еще раз с задержкой
                            if any(keyword in error_msg.lower() for keyword in ["cannot connect", "not reachable", "connection", "reset", "refused"]):
                                if attempt_num < len(attempts_no_profile):
                                    print(f"[ЛОГ] Ошибка подключения. Пробую еще раз...")
                                    time.sleep(3)
                                    continue
                                else:
                                    raise
                            elif attempt_num < len(attempts_no_profile):
                                print(f"[ЛОГ] Пробую следующую конфигурацию...")
                                time.sleep(2)
                                continue
                            else:
                                raise
                    
                    if driver is None:
                        raise Exception("Не удалось запустить Chrome после всех попыток")
            
            # Проверяем что driver создан
            if driver is None:
                raise Exception("Драйвер не был создан")
            
            print(f"[ЛОГ] ✓ WebDriver создан успешно")
            try:
                print(f"[ЛОГ] Session ID: {driver.session_id}")
                print(f"[ЛОГ] Capabilities: {driver.capabilities}")
            except Exception as e:
                print(f"[ЛОГ] ⚠ Не удалось получить информацию о сессии: {e}")
            
            # Скрываем webdriver
            try:
                driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": driver.execute_script("return navigator.userAgent").replace('Headless', '')
                })
            except Exception as e:
                print(f"[ЛОГ] ⚠ Не удалось установить User-Agent: {e}")
            
            return driver
            
        except (ConnectionResetError, ConnectionError, ConnectionAbortedError) as conn_error:
            import traceback
            print(f"\n{'='*60}")
            print(f"[ОШИБКА] Ошибка подключения к Chrome")
            print(f"{'='*60}")
            print(f"[ЛОГ] Тип: {type(conn_error).__name__}")
            print(f"[ЛОГ] Сообщение: {str(conn_error)}")
            print(f"{'='*60}\n")
            
            print(f"\n💡 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
            print(f"   1. Chrome запустился, но соединение было разорвано")
            print(f"   2. Антивирус или файрвол блокирует соединение")
            print(f"   3. Порт 9223 (remote-debugging-port) занят другим процессом")
            print(f"   4. Профиль поврежден или имеет проблемы с правами доступа")
            print(f"\n💡 РЕШЕНИЯ:")
            print(f"   1. Закройте ВСЕ окна Chrome: taskkill /F /IM chrome.exe")
            print(f"   2. Подождите 10 секунд и попробуйте снова")
            print(f"   3. Перезагрузите компьютер (если Chrome завис)")
            print(f"   4. Проверьте антивирус (может блокировать)")
            print(f"   5. Попробуйте запустить Chrome вручную и закройте его")
            print(f"   6. Удалите папку chrome_parser_profile и дайте парсеру создать новую")
            return None
            
        except Exception as e:
            import traceback
            print(f"\n{'='*60}")
            print(f"[ОШИБКА] Детальная информация")
            print(f"{'='*60}")
            print(f"[ЛОГ] Тип: {type(e).__name__}")
            print(f"[ЛОГ] Сообщение: {str(e)}")
            print(f"\n[ЛОГ] Полный traceback:")
            traceback.print_exc()
            print(f"{'='*60}\n")
            
            print(f"\n💡 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
            print(f"   1. Профиль '{CHROME_PROFILE_NAME}' используется другим процессом Chrome")
            print(f"   2. Профиль поврежден или имеет проблемы с правами доступа")
            print(f"   3. Несовместимость версий Chrome ({chrome_exe_path if BROWSER_TYPE == 'chrome' else 'Edge'}) и ChromeDriver")
            print(f"   4. Антивирус блокирует запуск Chrome через Selenium")
            print(f"\n💡 РЕШЕНИЯ:")
            print(f"   1. Закройте ВСЕ окна Chrome: taskkill /F /IM chrome.exe")
            print(f"   2. Подождите 10 секунд и попробуйте снова")
            print(f"   3. Попробуйте другой профиль (измените CHROME_PROFILE_NAME)")
            print(f"   4. Используйте Edge: BROWSER_TYPE = 'edge'")
            print(f"   5. Удалите папку chrome_parser_profile и дайте парсеру создать новую")
            return None


def human_delay(min_sec=1, max_sec=3):
    """Случайная задержка как у человека"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def parse_price_from_current_page(driver, article):
    """
    Парсит цену с текущей открытой страницы товара
    НЕ открывает и НЕ закрывает вкладки - это делает вызывающая функция
    Возвращает цену или 0 если товара нет в наличии
    """
    try:
        # Даем странице время полностью загрузиться перед началом парсинга
        time.sleep(1)
        
        # Проверяем на captcha
        if "Почти готово" in driver.title or "captcha" in driver.page_source.lower():
            print(f"  [{article}] ⚠ Captcha обнаружена!")
            return None  # None = нужна повторная попытка
        
        # КРИТИЧНО: Проверяем наличие элемента "Нет в наличии"
        try:
            sold_out_element = driver.find_element(By.CSS_SELECTOR, "h2[class*='soldOutProduct']")
            print(f"  [{article}] ⚠ Товар недоступен: {sold_out_element.text}")
            return 0
        except:
            pass  # Элемент не найден - товар в наличии
        
        # Дополнительная проверка по ключевым словам
        page_text = driver.page_source.lower()
        unavailable_keywords = ['нет в наличии', 'товар недоступен', 'недоступен для заказа', 'закончился', 'распродан']
        
        for keyword in unavailable_keywords:
            if keyword in page_text:
                print(f"  [{article}] ⚠ Товар недоступен: '{keyword}'")
                return 0
        
        # Кликаем на кнопку кошелька (если есть)
        try:
            wallet_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[class*='priceBlockWalletPrice']"))
            )
            wallet_button.click()
            time.sleep(1.5)  # Увеличена задержка для появления финальной цены
        except:
            pass  # Кнопки кошелька нет - это нормально
        
        # Ищем элемент с финальной ценой
        price_selectors = [
            (By.CSS_SELECTOR, "h2.mo-typography_color_primary"),
            (By.CSS_SELECTOR, "h2[class*='mo-typography'][class*='color_primary']"),
            (By.CSS_SELECTOR, "ins.priceBlockFinalPrice--iToZR"),
            (By.CSS_SELECTOR, "ins[class*='priceBlockFinalPrice']"),
            (By.CSS_SELECTOR, "ins.mo-typography[class*='priceBlockFinalPrice']"),
            (By.CSS_SELECTOR, "ins[class*='priceBlockFinalPrice'][class*='mo-typography']"),
            (By.CSS_SELECTOR, "ins[class*='FinalPrice']"),
            (By.CSS_SELECTOR, "span[class*='final-price']"),
            (By.CSS_SELECTOR, "ins[class*='price']"),
        ]
        
        price = None
        for by, selector in price_selectors:
            try:
                price_elem = WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((by, selector))
                )
                price_text = price_elem.text.strip()
                price_num = re.sub(r'[^\d]', '', price_text)
                if price_num:
                    price = int(price_num)
                    break
            except:
                continue
        
        if not price:
            # Если цена не найдена, подождем еще и попробуем снова
            print(f"  [{article}] ⚠ Цена не найдена с первой попытки, жду еще 3 секунды...")
            time.sleep(3)
            
            # Повторная попытка найти цену с увеличенным таймаутом
            for by, selector in price_selectors:
                try:
                    price_elem = WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    price_text = price_elem.text.strip()
                    price_num = re.sub(r'[^\d]', '', price_text)
                    if price_num:
                        price = int(price_num)
                        print(f"  [{article}] ✓ Цена найдена со второй попытки: {price} ₽")
                        break
                except:
                    continue
        
        if not price:
            print(f"  [{article}] ✗ Цена не найдена даже после повторной попытки")
            return 0
        
        return price
    
    except Exception as e:
        print(f"  [{article}] ✗ Ошибка парсинга: {e}")
        return 0


def process_products_parallel(driver, products):
    """
    Обрабатывает товары параллельно по PARALLEL_TABS штук
    Возвращает список результатов
    """
    results = []
    main_window = driver.window_handles[0]
    total = len(products)
    
    print(f"\n{'='*80}")
    print(f"ПАРАЛЛЕЛЬНАЯ ОБРАБОТКА: {PARALLEL_TABS} вкладок одновременно")
    print(f"{'='*80}\n")
    
    # Обрабатываем товары пачками
    for batch_start in range(0, total, PARALLEL_TABS):
        batch = products[batch_start : batch_start + PARALLEL_TABS]
        batch_num = batch_start // PARALLEL_TABS + 1
        total_batches = (total + PARALLEL_TABS - 1) // PARALLEL_TABS
        
        print(f"\n{'─'*80}")
        print(f"📦 ПАКЕТ {batch_num}/{total_batches} ({len(batch)} товаров)")
        print(f"{'─'*80}")
        
        # ФАЗА 1: Открыть все вкладки пакета
        print(f"\n[1/4] Открываю {len(batch)} вкладок...")
        for idx, product in enumerate(batch):
            print(f"  [{batch_start + idx + 1}/{total}] Открываю: {product['article']}")
            driver.execute_script("window.open(arguments[0], '_blank');", product['url'])
            time.sleep(0.3)  # Минимальная задержка между открытием вкладок
        
        # ФАЗА 2: Ждем загрузки всех вкладок
        print(f"\n[2/4] Жду полной загрузки страниц...")
        tabs = driver.window_handles[1:]  # Все вкладки кроме главной
        
        # Ждем 3 секунды для надежной загрузки страниц
        time.sleep(3)
        
        print(f"  ✓ Все {len(tabs)} вкладок загружены")
        
        # ФАЗА 3: Парсим цены из всех вкладок
        print(f"\n[3/4] Парсинг цен...")
        for idx, (tab_handle, product) in enumerate(zip(tabs, batch)):
            try:
                driver.switch_to.window(tab_handle)
                price = parse_price_from_current_page(driver, product['article'])
                
                # Если captcha - пропускаем
                if price is None:
                    price = 0
                
                results.append({
                    'url': product['url'],
                    'article': product['article'],
                    'price': price
                })
                
                status = f"{price} ₽" if price > 0 else "недоступен" if price == 0 else "ошибка"
                print(f"  [{batch_start + idx + 1}/{total}] {product['article']}: {status}")
            
            except Exception as e:
                print(f"  [{batch_start + idx + 1}/{total}] {product['article']}: ✗ ошибка - {e}")
                results.append({
                    'url': product['url'],
                    'article': product['article'],
                    'price': 0
                })
        
        # ФАЗА 4: Закрыть все вкладки пакета
        print(f"\n[4/4] Закрываю вкладки...")
        for tab_handle in tabs:
            try:
                driver.switch_to.window(tab_handle)
                driver.close()
            except:
                pass
        
        # Возвращаемся на главную вкладку
        driver.switch_to.window(main_window)
        
        # Промежуточное сохранение
        if SAVE_INTERMEDIATE_RESULTS and len(results) % SAVE_EVERY_N_PRODUCTS == 0:
            print(f"\n💾 Промежуточное сохранение ({len(results)} товаров)...")
            if save_results_to_excel(results, OUTPUT_EXCEL_FILE):
                print(f"✓ Сохранено")
        
        # Задержка между пакетами
        if batch_start + PARALLEL_TABS < total:
            delay = random.uniform(*DELAY_BETWEEN_BATCHES)
            print(f"\n⏸ Пауза {delay:.1f}с перед следующим пакетом...\n")
            time.sleep(delay)
    
    return results


def get_price_from_product_page(driver, product_url, article):
    """
    Открывает карточку товара по ссылке и извлекает цену
    Возвращает цену или 0 если товара нет в наличии
    """
    try:
        print(f"\n[{article}] Открываю карточку в новой вкладке...")
        print(f"  URL: {product_url}")
        
        # Открываем в новой вкладке того же окна
        driver.execute_script("window.open(arguments[0], '_blank');", product_url)
        
        # Переключаемся на новую вкладку
        driver.switch_to.window(driver.window_handles[-1])
        
        human_delay(2, 4)
        
        # Проверяем на captcha
        if "Почти готово" in driver.title or "captcha" in driver.page_source.lower():
            print(f"  ⚠ Captcha! Жду 10 сек...")
            time.sleep(10)
            driver.get(product_url)
            human_delay(2, 4)
        
        # КРИТИЧНО: Проверяем наличие элемента "Нет в наличии"
        # <h2 class="... soldOutProduct--vCzrv">Нет в наличии</h2>
        try:
            sold_out_element = driver.find_element(By.CSS_SELECTOR, "h2[class*='soldOutProduct']")
            print(f"  ⚠ Товар недоступен: найден элемент 'soldOutProduct' - {sold_out_element.text}")
            # Закрываем вкладку и пропускаем товар
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            return 0
        except:
            pass  # Элемент не найден - товар в наличии
        
        # Дополнительная проверка по ключевым словам (fallback)
        page_text = driver.page_source.lower()
        unavailable_keywords = [
            'нет в наличии',
            'товар недоступен',
            'недоступен для заказа',
            'закончился',
            'распродан'
        ]
        
        is_unavailable = False
        for keyword in unavailable_keywords:
            if keyword in page_text:
                is_unavailable = True
                print(f"  ⚠ Товар недоступен: найдено '{keyword}'")
                break
        
        if is_unavailable:
            # Закрываем вкладку если товар недоступен
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            return 0
        
        # НОВАЯ ЛОГИКА: Сначала кликаем на кнопку кошелька (если есть)
        # Это открывает финальную цену с учетом всех скидок
        try:
            # Ищем кнопку с кошельком (класс priceBlockWalletPrice)
            wallet_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[class*='priceBlockWalletPrice']"))
            )
            print(f"  ⚠ Найдена кнопка кошелька, кликаю...")
            wallet_button.click()
            human_delay(1, 2)  # Ждем появления финальной цены
        except:
            # Кнопки кошелька нет - это нормально, продолжаем
            print(f"  ℹ Кнопка кошелька не найдена, ищу обычную цену")
        
        # Ищем элемент с финальной ценой
        # Приоритет 1: h2 с классом mo-typography_color_primary (появляется после клика на кошелек)
        # Приоритет 2: ins.priceBlockFinalPrice (обычная цена)
        price_selectors = [
            # Финальная цена после клика на кошелек
            (By.CSS_SELECTOR, "h2.mo-typography_color_primary"),
            (By.CSS_SELECTOR, "h2[class*='mo-typography'][class*='color_primary']"),
            # Обычная цена
            (By.CSS_SELECTOR, "ins.priceBlockFinalPrice--iToZR"),
            (By.CSS_SELECTOR, "ins[class*='priceBlockFinalPrice']"),
            (By.CSS_SELECTOR, "ins.mo-typography[class*='priceBlockFinalPrice']"),
            (By.CSS_SELECTOR, "ins[class*='priceBlockFinalPrice'][class*='mo-typography']"),
            # Fallback селекторы
            (By.CSS_SELECTOR, "ins[class*='FinalPrice']"),
            (By.CSS_SELECTOR, "span[class*='final-price']"),
            (By.CSS_SELECTOR, "ins[class*='price']"),
        ]
        
        price = None
        for by, selector in price_selectors:
            try:
                price_elem = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((by, selector))
                )
                price_text = price_elem.text.strip()
                # Извлекаем число (убираем все нецифровые символы, включая nbsp)
                price_num = re.sub(r'[^\d]', '', price_text)
                if price_num:
                    price = int(price_num)
                    print(f"  ✓ Цена найдена: {price} ₽ (селектор: {selector})")
                    break
            except:
                continue
        
        if not price:
            print(f"  ⚠ Цена не найдена - возможно товар недоступен")
            # Закрываем вкладку перед возвратом
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            return 0
        
        # Закрываем вкладку после успешного парсинга
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        
        return price
    
    except InvalidSessionIdException:
        print(f"  ✗ Сессия Chrome разорвана")
        raise  # Пробрасываем дальше для переподключения
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
        # Закрываем вкладку в случае ошибки (если она открыта)
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
        except:
            pass
        return 0


def save_results_to_excel(results, output_file):
    """Сохраняет результаты в Excel файл"""
    try:
        from openpyxl import Workbook
        
        # Создаём новый Excel файл
        wb_out = Workbook()
        ws_out = wb_out.active
        ws_out.title = "Цены"
        
        # Заголовки
        ws_out.append(["ссылка на товар", "артикул", "цена"])
        
        # Данные
        for result in results:
            ws_out.append([
                result['url'],
                result['article'],
                result['price']
            ])
        
        # Автофильтр
        ws_out.auto_filter.ref = ws_out.dimensions
        
        # Сохраняем файл
        wb_out.save(output_file)
        wb_out.close()
        
        return True
    except Exception as e:
        print(f"\n[!] ОШИБКА при сохранении: {e}")
        return False


def main():
    print("\n" + "="*80)
    print("ПАРСЕР ЦЕН WB - ПРОСТОЙ ПАРСЕР")
    print("="*80)
    
    # Проверяем путь к профилю (если не используем remote и не используем временный профиль)
    if not USE_REMOTE_CHROME and not USE_TEMP_PROFILE:
        if not os.path.exists(CHROME_USER_DATA_DIR):
            print(f"\n[!] ОШИБКА: Не найден Chrome User Data: {CHROME_USER_DATA_DIR}")
            return
        
        profile_path = os.path.join(CHROME_USER_DATA_DIR, CHROME_PROFILE_NAME)
        if not os.path.exists(profile_path):
            print(f"\n[!] ОШИБКА: Не найден профиль: {profile_path}")
            print(f"    Доступные профили:")
            for item in os.listdir(CHROME_USER_DATA_DIR):
                if item.startswith('Profile') or item == 'Default':
                    print(f"      - {item}")
            return
    
    print(f"\n✓ Конфигурация проверена")
    
    # Загружаем Excel со ссылками
    try:
        wb = load_workbook(LINKS_EXCEL_FILE)
    except Exception as e:
        print(f"\n[!] ОШИБКА открытия Excel: {e}")
        print(f"    Убедись что файл '{LINKS_EXCEL_FILE}' закрыт!")
        print(f"    Сначала запусти Create_Links_Excel.py для создания файла со ссылками")
        return
    
    ws_in = wb[SHEET_LINKS]
    
    # Загружаем ссылки и артикулы
    products = []
    for row in ws_in.iter_rows(min_row=2, max_col=2, values_only=True):
        if row[0] and row[1]:  # ссылка и артикул
            products.append({
                'url': str(row[0]).strip(),
                'article': str(row[1]).strip()
            })
    
    print(f"\n[1/3] Найдено товаров: {len(products)}")
    
    if len(products) == 0:
        print("[!] Нет товаров для обработки!")
        print(f"    Сначала запусти Create_Links_Excel.py для создания файла со ссылками")
        wb.close()
        return
    
    # ТЕСТОВЫЙ РЕЖИМ: ограничиваем количество товаров
    if TEST_MODE:
        products = products[:TEST_PRODUCTS_COUNT]
        print(f"⚠️  ТЕСТОВЫЙ РЕЖИМ: обработка первых {len(products)} товаров")
    
    # Запускаем Chrome
    print(f"\n[2/3] Запуск Chrome...")
    
    driver = None
    results = []  # Инициализируем результаты вне try, чтобы сохранить в finally
    try:
        driver = setup_browser_driver()
        
        if not driver:
            print("\n[!] Не удалось запустить Chrome!")
            if USE_REMOTE_CHROME:
                print(f"\n💡 Убедись что Chrome запущен через START_CHROME_DEBUG.bat")
            wb.close()
            return
        
        print("    ✓ Chrome запущен")
        
        # Пауза для ручной авторизации (только в видимом режиме)
        if WAIT_FOR_MANUAL_LOGIN and not HEADLESS_MODE:
            print(f"\n{'='*80}")
            print("⏸  ПАУЗА ДЛЯ АВТОРИЗАЦИИ")
            print(f"{'='*80}")
            print(f"\n📋 ИНСТРУКЦИЯ:")
            print(f"   1. В открывшемся Chrome зайдите на сайт WB")
            print(f"   2. Авторизуйтесь в своем аккаунте")
            print(f"   3. Установите правильный адрес доставки")
            print(f"   4. После этого вернитесь сюда и нажмите ENTER")
            print(f"\n⏱  Таймаут: {MANUAL_LOGIN_TIMEOUT} секунд")
            print(f"   (или нажмите ENTER когда будете готовы)")
            print(f"\n{'='*80}\n")
        elif WAIT_FOR_MANUAL_LOGIN and HEADLESS_MODE:
            print(f"\n⚠️  ВНИМАНИЕ: Headless режим активен!")
            print(f"   Авторизация через браузер невозможна (браузер не виден).")
            print(f"   Убедитесь, что профиль уже авторизован или используйте видимый режим для первой авторизации.\n")
            # В headless режиме просто проверяем, что профиль работает
            try:
                print(f"[ЛОГ] Проверяю доступность WB...")
                driver.get("https://www.wildberries.ru/")
                time.sleep(2)
                print(f"[ЛОГ] ✓ WB доступен, продолжаю парсинг...")
            except Exception as e:
                print(f"\n[!] Ошибка при проверке WB: {e}")
                print(f"    Продолжаю парсинг...")
        
        # Парсим товары (параллельно)
        print(f"\n[3/3] Парсинг цен...")
        print("="*80)
        
        # Используем параллельную обработку
        results = process_products_parallel(driver, products)
        
    except Exception as e:
        print(f"\n[!] КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Сохраняем результаты в Excel файл (всегда, даже при ошибках)
        print(f"\n{'='*80}")
        print("ФИНАЛЬНОЕ СОХРАНЕНИЕ РЕЗУЛЬТАТОВ")
        print(f"{'='*80}")
        
        if save_results_to_excel(results, OUTPUT_EXCEL_FILE):
            print(f"\n✓ Сохранено: {len(results)} товаров")
            print(f"✓ Файл: {OUTPUT_EXCEL_FILE}")
        
        if driver:
            print(f"\n[Закрываю Chrome через 5 секунд...]")
            time.sleep(5)
            driver.quit()
        
        wb.close()
    
    print(f"\n{'='*80}")
    print("ЗАВЕРШЕНО")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
