# -*- coding: utf-8 -*-
"""
ПАРСЕР ЦЕН WILDBERRIES - ДОПАРСИНГ НЕДОСТАЮЩИХ АРТИКУЛОВ
Парсит цены для конкретного списка артикулов и сохраняет в Excel файл

ИНСТРУКЦИЯ:
1. Убедитесь что Chrome закрыт (или используйте remote режим)
2. Запустите: python parsers/Parser_WB_Missing.py
3. Подтвердите логин и адрес доставки в браузере
4. Результаты сохраняются в data/missing_articles_results.xlsx
"""

import os
import sys
import time
import random
import re
import subprocess
import shutil
from selenium import webdriver

# Загрузка переменных окружения из .env файла
try:
    from dotenv import load_dotenv
    PROJECT_ROOT_TEMP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(PROJECT_ROOT_TEMP, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"[ЛОГ] Загружены настройки из .env файла")
except ImportError:
    print("[ЛОГ] python-dotenv не установлен, используются настройки по умолчанию")
except Exception as e:
    print(f"[ЛОГ] Ошибка загрузки .env: {e}, используются настройки по умолчанию")

# Настройка кодировки консоли для Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, InvalidSessionIdException
from openpyxl import Workbook
import undetected_chromedriver as uc

# Конфигурация
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Функция для чтения настроек из .env
def get_env_bool(key, default=False):
    value = os.getenv(key, str(default)).strip().lower()
    return value in ('true', '1', 'yes', 'on')

def get_env_int(key, default=0):
    try:
        return int(os.getenv(key, str(default)))
    except:
        return default

def get_env_str(key, default=""):
    return os.getenv(key, default)

# Настройки браузера
BROWSER_TYPE = get_env_str("BROWSER_TYPE", "chrome").lower()
HEADLESS_MODE = get_env_bool("HEADLESS_MODE", True)
USE_REMOTE_CHROME = get_env_bool("USE_REMOTE_CHROME", False)
CHROME_DEBUG_PORT = get_env_int("CHROME_DEBUG_PORT", 9222)
USE_TEMP_PROFILE = get_env_bool("USE_TEMP_PROFILE", True)
TEMP_PROFILE_DIR = os.path.join(PROJECT_ROOT, "chrome_parser_profile")
COPY_PROFILE_DATA = get_env_bool("COPY_PROFILE_DATA", True)
SOURCE_PROFILE_FOR_COPY = get_env_str("SOURCE_PROFILE_FOR_COPY", "Profile 4")
WAIT_FOR_MANUAL_LOGIN = get_env_bool("WAIT_FOR_MANUAL_LOGIN", True)
MANUAL_LOGIN_TIMEOUT = get_env_int("MANUAL_LOGIN_TIMEOUT", 120)

# Настройки парсинга
PARALLEL_TABS = get_env_int("PARALLEL_TABS", 20)

# СПИСОК АРТИКУЛОВ ДЛЯ ПАРСИНГА
MISSING_ARTICLES = [
    "102136669", "102141007", "102141974", "102175052", "106682406",
    "109291881", "109511802", "109781394", "109787865", "110572701",
    "111035235", "111036561", "111428910", "111495893", "111677765",
    "111682661", "111682921", "114311950", "114391690", "114392598",
    "115216754", "115224606", "115692124", "115819519", "115820242",
    "115821448", "115822290", "115823594", "115826544", "117781871",
    "118203193", "119038099", "119899275", "119933902", "119936769",
    "119947092", "119953409", "120005553", "120006479", "120192128",
    "120262417", "12061123", "12061124", "12061125", "12061126",
    "12061127", "12061128", "12061129", "12061130", "12061131",
    "12061132", "12061133", "12061134", "12061135", "12061136",
    "12061138", "12061139", "12061140", "12061141"
]

OUTPUT_EXCEL_FILE = os.path.join(DATA_DIR, "missing_articles_results.xlsx")


def check_remote_chrome_available():
    """Проверяет доступность remote Chrome"""
    try:
        import requests
        response = requests.get(f"http://127.0.0.1:{CHROME_DEBUG_PORT}/json", timeout=2)
        return response.status_code == 200
    except:
        return False


def cleanup_profile_locks(profile_path):
    """Очищает lock-файлы профиля Chrome"""
    lock_files = [
        "SingletonLock",
        "lockfile",
        "SingletonSocket",
        "SingletonCookie",
        "Default/DevToolsActivePort"
    ]
    
    cleaned = False
    for lock_file in lock_files:
        lock_path = os.path.join(profile_path, lock_file)
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
                cleaned = True
            except:
                pass
    
    return cleaned


def copy_profile_data(source_profile, dest_profile):
    """Копирует данные из исходного профиля в профиль парсера"""
    if not os.path.exists(source_profile):
        print(f"[ЛОГ] Источник не найден: {source_profile}")
        return False
    
    os.makedirs(dest_profile, exist_ok=True)
    
    files_to_copy = [
        "Cookies",
        "Cookies-journal",
        "Network/Cookies",
        "Network/Cookies-journal",
        "Login Data",
        "Login Data-journal",
        "Preferences",
        "Web Data",
        "Web Data-journal",
        "History",
        "History-journal"
    ]
    
    dirs_to_copy = [
        "Local Storage",
        "Session Storage",
        "IndexedDB"
    ]
    
    copied_count = 0
    for item in files_to_copy:
        src_path = os.path.join(source_profile, item)
        dest_path = os.path.join(dest_profile, item)
        
        if os.path.exists(src_path):
            try:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(src_path, dest_path)
                copied_count += 1
            except Exception as e:
                print(f"[ЛОГ] - Файл не найден: {item}")
        else:
            print(f"[ЛОГ] - Файл не найден: {item}")
    
    for dir_name in dirs_to_copy:
        src_dir = os.path.join(source_profile, dir_name)
        dest_dir = os.path.join(dest_profile, dir_name)
        
        if os.path.exists(src_dir):
            try:
                shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)
                copied_count += 1
            except Exception as e:
                print(f"[ЛОГ] - Директория не найдена: {dir_name}")
        else:
            print(f"[ЛОГ] - Директория не найдена: {dir_name}")
    
    return copied_count > 0


def setup_browser_driver():
    """Настраивает браузер Chrome"""
    print(f"\n{'='*60}")
    print(f"[ДИАГНОСТИКА] Настройка браузера CHROME")
    print(f"{'='*60}")
    
    if USE_REMOTE_CHROME:
        print(f"[ЛОГ] Режим: Remote подключение")
        options = ChromeOptions()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{CHROME_DEBUG_PORT}")
        try:
            driver = webdriver.Chrome(options=options)
            return driver
        except Exception as e:
            print(f"\n[!] ОШИБКА подключения к Chrome: {e}")
            return None
    else:
        print(f"[ЛОГ] Режим: Прямой запуск браузера")
        
        if USE_TEMP_PROFILE and COPY_PROFILE_DATA:
            # Копируем данные профиля
            chrome_user_data = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
            source_profile = os.path.join(chrome_user_data, SOURCE_PROFILE_FOR_COPY)
            
            print(f"\n{'='*60}")
            print(f"[КОПИРОВАНИЕ] Перенос данных из {SOURCE_PROFILE_FOR_COPY}")
            print(f"{'='*60}")
            print(f"[ЛОГ] Источник: {source_profile}")
            print(f"[ЛОГ] Назначение: {TEMP_PROFILE_DIR}")
            
            copy_profile_data(source_profile, TEMP_PROFILE_DIR)
            cleanup_profile_locks(TEMP_PROFILE_DIR)
        
        # Пробуем несколько конфигураций
        attempts = [
            {'use_subprocess': True, 'version_main': None, 'user_data_dir': None},
            {'use_subprocess': True, 'version_main': None, 'user_data_dir': TEMP_PROFILE_DIR if USE_TEMP_PROFILE else None},
            {'use_subprocess': False, 'version_main': None, 'user_data_dir': TEMP_PROFILE_DIR if USE_TEMP_PROFILE else None},
        ]
        
        for attempt_num, attempt_config in enumerate(attempts, 1):
            try:
                print(f"[ЛОГ] Попытка {attempt_num}/{len(attempts)} запуска Chrome...")
                
                options = ChromeOptions()
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--no-sandbox")
                
                driver_kwargs = {
                    'headless': HEADLESS_MODE,
                    'use_subprocess': attempt_config['use_subprocess'],
                    'version_main': attempt_config['version_main'],
                    'options': options
                }
                
                user_dir = attempt_config.get('user_data_dir')
                if user_dir is not None:
                    driver_kwargs['user_data_dir'] = user_dir
                    print(f"[ЛОГ] Использую профиль: {user_dir}")
                else:
                    print(f"[ЛОГ] Запускаю Chrome без профиля (временный профиль)")
                
                driver = uc.Chrome(**driver_kwargs)
                
                print(f"[ЛОГ] Chrome драйвер создан, жду инициализацию Chrome...")
                time.sleep(5)
                
                max_retries = 3
                driver_works = False
                for retry in range(max_retries):
                    try:
                        driver.current_url
                        print(f"[ЛОГ] ✓ Chrome драйвер создан успешно и отвечает")
                        driver_works = True
                        break
                    except Exception as check_error:
                        if retry < max_retries - 1:
                            print(f"[ЛОГ] ⚠ Попытка {retry + 1}/{max_retries}: драйвер еще не готов, жду еще 2 секунды...")
                            time.sleep(2)
                        else:
                            print(f"[ЛОГ] ⚠ Драйвер создан, но не отвечает после {max_retries} попыток")
                            try:
                                driver.quit()
                            except:
                                pass
                            driver = None
                            driver_works = False
                
                if driver_works:
                    return driver
                elif attempt_num < len(attempts):
                    print(f"[ЛОГ] Пробую следующую конфигурацию...")
                    time.sleep(2)
                    continue
                else:
                    raise Exception("Chrome драйвер не отвечает после всех попыток")
                    
            except Exception as e:
                print(f"[ЛОГ] ✗ Ошибка создания Chrome драйвера: {e}")
                if attempt_num < len(attempts):
                    print(f"[ЛОГ] Пробую следующую конфигурацию...")
                    time.sleep(2)
                    continue
                else:
                    raise
        
        return None


def parse_price_from_current_page(driver, article, product_url=None):
    """Парсит цены с текущей открытой страницы товара"""
    try:
        time.sleep(0.5)
        
        page_source_lower = driver.page_source.lower()
        if "Почти готово" in driver.title or "captcha" in page_source_lower:
            print(f"  [{article}] ⚠ Captcha обнаружена!")
            return None
        
        if "подозрительная активность" in page_source_lower:
            print(f"  [{article}] ⚠⚠⚠ WB ЗАБЛОКИРОВАЛ!")
            return None
        
        # Проверяем "Нет в наличии"
        try:
            sold_out_element = driver.find_element(By.CSS_SELECTOR, "h2[class*='soldOutProduct']")
            print(f"  [{article}] ⚠ Товар недоступен: {sold_out_element.text}")
            return {'price': 0, 'price_with_card': 0}
        except:
            pass
        
        unavailable_keywords = ['нет в наличии', 'товар недоступен', 'недоступен для заказа']
        for keyword in unavailable_keywords:
            if keyword in page_source_lower:
                print(f"  [{article}] ⚠ Товар недоступен: '{keyword}'")
                return {'price': 0, 'price_with_card': 0}
        
        # Кликаем на кнопку кошелька
        try:
            wallet_button = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[class*='priceBlockWalletPrice']"))
            )
            wallet_button.click()
            time.sleep(0.5)
        except:
            pass
        
        # Ищем цены
        price_selectors = [
            (By.CSS_SELECTOR, "h2.mo-typography_color_primary"),
            (By.CSS_SELECTOR, "h2[class*='mo-typography'][class*='color_primary']"),
            (By.CSS_SELECTOR, "ins.priceBlockFinalPrice--iToZR"),
            (By.CSS_SELECTOR, "ins[class*='priceBlockFinalPrice']"),
        ]
        
        price_with_card_selectors = [
            (By.CSS_SELECTOR, "h2.mo-typography_color_danger"),
            (By.CSS_SELECTOR, "h2[class*='mo-typography'][class*='color_danger']"),
        ]
        
        price = None
        price_with_card = None
        
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
        
        for by, selector in price_with_card_selectors:
            try:
                price_card_elem = driver.find_element(by, selector)
                price_card_text = price_card_elem.text.strip()
                price_card_num = re.sub(r'[^\d]', '', price_card_text)
                if price_card_num:
                    price_with_card = int(price_card_num)
                    break
            except:
                continue
        
        # Если цена не найдена, перезагружаем страницу
        if not price:
            print(f"  [{article}] ⚠ Цена не найдена, перезагружаю страницу...")
            try:
                if product_url:
                    driver.get(product_url)
                else:
                    driver.get(driver.current_url)
                time.sleep(5)
                
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
                
                if not price_with_card:
                    for by, selector in price_with_card_selectors:
                        try:
                            price_card_elem = driver.find_element(by, selector)
                            price_card_text = price_card_elem.text.strip()
                            price_card_num = re.sub(r'[^\d]', '', price_card_text)
                            if price_card_num:
                                price_with_card = int(price_card_num)
                                break
                        except:
                            continue
            except Exception as e:
                print(f"  [{article}] ⚠ Ошибка перезагрузки: {e}")
        
        if not price:
            print(f"  [{article}] ✗ Цена не найдена")
            return {'price': 0, 'price_with_card': 0}
        
        return {
            'price': price,
            'price_with_card': price_with_card if price_with_card else 0
        }
    
    except Exception as e:
        print(f"  [{article}] ✗ Ошибка парсинга: {e}")
        return {'price': 0, 'price_with_card': 0}


def process_articles_parallel(driver, articles):
    """Обрабатывает артикулы параллельно"""
    results = []
    
    # Формируем список товаров с URL
    products = []
    for article in articles:
        products.append({
            'url': f"https://www.wildberries.ru/catalog/{article}/detail.aspx",
            'article': article
        })
    
    total = len(products)
    print(f"\n{'='*80}")
    print(f"ПАРАЛЛЕЛЬНАЯ ОБРАБОТКА: {PARALLEL_TABS} вкладок одновременно")
    print(f"Всего артикулов: {total}")
    print(f"{'='*80}\n")
    
    try:
        main_window = driver.window_handles[0]
    except Exception as e:
        print(f"\n[!] ОШИБКА: Браузер закрыт: {e}")
        return results
    
    # Обрабатываем пачками
    for batch_start in range(0, total, PARALLEL_TABS):
        batch = products[batch_start : batch_start + PARALLEL_TABS]
        batch_num = batch_start // PARALLEL_TABS + 1
        total_batches = (total + PARALLEL_TABS - 1) // PARALLEL_TABS
        
        print(f"\n{'─'*80}")
        print(f"📦 ПАКЕТ {batch_num}/{total_batches} ({len(batch)} артикулов)")
        print(f"{'─'*80}")
        
        # ФАЗА 1: Открываем все вкладки
        print(f"\n[1/4] Открываю {len(batch)} вкладок...")
        driver.switch_to.window(main_window)
        
        initial_handles_count = len(driver.window_handles)
        opened_tabs_map = {}
        
        for idx, product in enumerate(batch):
            try:
                print(f"  [{batch_start + idx + 1}/{total}] Открываю: {product['article']}")
                driver.execute_script("window.open(arguments[0], '_blank');", product['url'])
                time.sleep(0.1)
                
                try:
                    all_handles = driver.window_handles
                    if len(all_handles) > initial_handles_count + idx:
                        new_tab_handle = all_handles[-1]
                        opened_tabs_map[new_tab_handle] = product
                        driver.switch_to.window(new_tab_handle)
                        time.sleep(0.1)
                        driver.switch_to.window(main_window)
                except Exception as tab_error:
                    print(f"      [ЛОГ] ⚠ Ошибка при сохранении соответствия: {tab_error}")
                
                print(f"      [ЛОГ] Вкладок после открытия: {len(driver.window_handles)}")
            except Exception as e:
                print(f"  [{batch_start + idx + 1}/{total}] ⚠ Ошибка: {e}")
        
        # ФАЗА 2: Ждем загрузки
        print(f"\n[2/4] Жду полной загрузки страниц...")
        time.sleep(1.5)  # Увеличена задержка для загрузки вкладок
        
        try:
            all_handles = driver.window_handles
            tabs = [h for h in all_handles if h != main_window]
            print(f"  [ЛОГ] Всего окон: {len(all_handles)}, вкладок для парсинга: {len(tabs)}")
            
            # Если вкладки не открылись, пробуем еще раз
            if len(tabs) == 0:
                print(f"  ⚠ ВНИМАНИЕ: Вкладки не открылись! Пробую еще раз...")
                driver.switch_to.window(main_window)
                for idx, product in enumerate(batch):
                    try:
                        driver.execute_script(f"window.open('{product['url']}', '_blank');")
                        time.sleep(0.2)
                        if len(driver.window_handles) > initial_handles_count + idx + 1:
                            driver.switch_to.window(driver.window_handles[-1])
                            time.sleep(0.1)
                            driver.switch_to.window(main_window)
                    except Exception as e:
                        print(f"  [ЛОГ] Ошибка при повторном открытии вкладки {idx+1}: {e}")
                time.sleep(0.5)
                try:
                    all_handles = driver.window_handles
                    tabs = [h for h in all_handles if h != main_window]
                    print(f"  [ЛОГ] После повторной попытки: {len(tabs)} вкладок")
                except:
                    tabs = []
        except Exception as e:
            print(f"  ⚠ Ошибка получения вкладок: {e}")
            tabs = []
        
        if not opened_tabs_map and len(tabs) == len(batch):
            for idx, tab_handle in enumerate(tabs):
                if idx < len(batch):
                    opened_tabs_map[tab_handle] = batch[idx]
        
        print(f"  ✓ Все {len(tabs)} вкладок загружены")
        
        # ФАЗА 3: Парсим цены
        print(f"\n[3/4] Парсинг цен...")
        
        tab_to_product = {}
        if opened_tabs_map:
            tab_to_product = opened_tabs_map.copy()
        else:
            for tab_handle in tabs:
                try:
                    driver.switch_to.window(tab_handle)
                    time.sleep(0.1)
                    current_url = driver.current_url
                    for product in batch:
                        if product['article'] in current_url or product['url'] in current_url:
                            tab_to_product[tab_handle] = product
                            break
                except:
                    continue
        
        for idx, product in enumerate(batch):
            try:
                matching_tab = None
                for tab_handle, tab_product in tab_to_product.items():
                    if tab_product['article'] == product['article']:
                        matching_tab = tab_handle
                        break
                
                if not matching_tab:
                    if idx < len(tabs):
                        matching_tab = tabs[idx]
                        try:
                            driver.switch_to.window(matching_tab)
                            current_url = driver.current_url
                            if product['article'] not in current_url and product['url'] not in current_url:
                                # Ищем правильную вкладку
                                found = False
                                for tab_handle in tabs:
                                    try:
                                        driver.switch_to.window(tab_handle)
                                        tab_url = driver.current_url
                                        if product['article'] in tab_url or product['url'] in tab_url:
                                            matching_tab = tab_handle
                                            found = True
                                            break
                                    except:
                                        continue
                                if not found:
                                    print(f"  [{batch_start + idx + 1}/{total}] ✗ Не найдена вкладка для {product['article']}")
                                    results.append({
                                        'url': product['url'],
                                        'article': product['article'],
                                        'price': 0,
                                        'price_with_card': 0
                                    })
                                    continue
                        except:
                            pass
                    else:
                        print(f"  [{batch_start + idx + 1}/{total}] ⚠ Вкладка не найдена для {product['article']}")
                        results.append({
                            'url': product['url'],
                            'article': product['article'],
                            'price': 0,
                            'price_with_card': 0
                        })
                        continue
                
                driver.switch_to.window(matching_tab)
                
                # Финальная проверка соответствия
                try:
                    current_url = driver.current_url
                    if product['article'] not in current_url and product['url'] not in current_url:
                        print(f"  [{batch_start + idx + 1}/{total}] ⚠ КРИТИЧНО: На вкладке неверный товар!")
                        print(f"      Ожидается: {product['article']}")
                        print(f"      На вкладке: {current_url[:80]}...")
                        found = False
                        for tab_handle in tabs:
                            try:
                                driver.switch_to.window(tab_handle)
                                tab_url = driver.current_url
                                if product['article'] in tab_url or product['url'] in tab_url:
                                    matching_tab = tab_handle
                                    found = True
                                    break
                            except:
                                continue
                        if not found:
                            print(f"  [{batch_start + idx + 1}/{total}] ✗ Не найдена правильная вкладка")
                            results.append({
                                'url': product['url'],
                                'article': product['article'],
                                'price': 0,
                                'price_with_card': 0
                            })
                            continue
                except:
                    pass
                
                price_data = parse_price_from_current_page(driver, product['article'], product['url'])
                
                if price_data is None:
                    price_data = {'price': 0, 'price_with_card': 0}
                
                if isinstance(price_data, (int, float)):
                    price_data = {'price': int(price_data), 'price_with_card': 0}
                
                results.append({
                    'url': product['url'],
                    'article': product['article'],
                    'price': price_data['price'],
                    'price_with_card': price_data.get('price_with_card', 0)
                })
                
                price = price_data['price']
                price_card = price_data.get('price_with_card', 0)
                if price_card and price_card > 0:
                    status = f"{price} ₽ / {price_card} ₽ (с картой)"
                else:
                    status = f"{price} ₽" if price > 0 else "недоступен" if price == 0 else "ошибка"
                print(f"  [{batch_start + idx + 1}/{total}] {product['article']}: {status}")
            
            except Exception as e:
                print(f"  [{batch_start + idx + 1}/{total}] {product['article']}: ✗ ошибка - {e}")
                results.append({
                    'url': product['url'],
                    'article': product['article'],
                    'price': 0,
                    'price_with_card': 0
                })
        
        # ФАЗА 4: Закрываем вкладки
        print(f"\n[4/4] Закрываю вкладки...")
        for tab_handle in tabs:
            try:
                driver.switch_to.window(tab_handle)
                driver.close()
            except:
                pass
        
        try:
            driver.switch_to.window(main_window)
        except:
            main_window = driver.window_handles[0]
            driver.switch_to.window(main_window)
        
        if batch_start + PARALLEL_TABS < total:
            time.sleep(0.5)
    
    return results


def save_results_to_excel(results, output_file):
    """Сохраняет результаты в Excel файл"""
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Результаты"
        
        # Заголовки
        ws.append(["ссылка на товар", "артикул", "цена", "цена с картой"])
        
        # Данные
        for result in results:
            ws.append([
                result['url'],
                result['article'],
                result['price'],
                result.get('price_with_card', 0)
            ])
        
        wb.save(output_file)
        print(f"\n✓ Результаты сохранены в: {output_file}")
        return True
    except Exception as e:
        print(f"\n[!] ОШИБКА при сохранении: {e}")
        return False


def main():
    print("\n" + "="*80)
    print("ПАРСЕР ЦЕН WB - ДОПАРСИНГ НЕДОСТАЮЩИХ АРТИКУЛОВ")
    print("="*80)
    
    print(f"\n✓ Конфигурация проверена")
    print(f"  Всего артикулов для обработки: {len(MISSING_ARTICLES)}")
    
    # Запускаем Chrome
    print(f"\n[1/3] Запуск Chrome...")
    driver = None
    results = []
    
    try:
        driver = setup_browser_driver()
        
        if not driver:
            print("\n[!] Не удалось запустить Chrome!")
            return
        
        print("    ✓ Chrome запущен")
        
        # Пауза для ручной авторизации
        if WAIT_FOR_MANUAL_LOGIN and not HEADLESS_MODE:
            print(f"\n{'='*80}")
            print("⏸  ПАУЗА ДЛЯ АВТОРИЗАЦИИ")
            print(f"{'='*80}")
            print(f"\n📋 ИНСТРУКЦИЯ:")
            print(f"   1. Открываю сайт WB в браузере...")
            print(f"   2. Авторизуйтесь в своем аккаунте")
            print(f"   3. Установите правильный адрес доставки")
            print(f"   4. После этого вернитесь сюда и нажмите ENTER")
            print(f"\n⏱  Таймаут: {MANUAL_LOGIN_TIMEOUT} секунд")
            print(f"{'='*80}\n")
            
            try:
                print(f"[ЛОГ] Открываю https://www.wildberries.ru/ для авторизации...")
                driver.get("https://www.wildberries.ru/")
                time.sleep(2)
                print(f"[ЛОГ] ✓ Страница WB открыта")
            except Exception as e:
                print(f"[ЛОГ] ⚠ Ошибка открытия WB: {e}")
            
            try:
                input(f"\n⏸ Нажмите ENTER когда авторизуетесь и установите адрес доставки...")
            except KeyboardInterrupt:
                print(f"\n[!] Прервано пользователем")
                driver.quit()
                return
            
            # Открываем тестовую вкладку для подтверждения разрешения на открытие вкладок
            print(f"\n{'='*80}")
            print("⏸  ПОДТВЕРЖДЕНИЕ РАЗРЕШЕНИЯ НА ОТКРЫТИЕ ВКЛАДОК")
            print(f"{'='*80}")
            print(f"\n📋 ИНСТРУКЦИЯ:")
            print(f"   1. Сейчас открою тестовую вкладку с товаром...")
            print(f"   2. В браузере появится запрос: 'Разрешить этому сайту открывать вкладки?'")
            print(f"   3. Нажмите 'РАЗРЕШИТЬ' или 'ALLOW' в браузере")
            print(f"   4. После этого вернитесь сюда и нажмите ENTER")
            print(f"{'='*80}\n")
            
            try:
                # Открываем тестовую вкладку с первым товаром из списка
                test_url = f"https://www.wildberries.ru/catalog/{MISSING_ARTICLES[0]}/detail.aspx"
                print(f"[ЛОГ] Открываю тестовую вкладку: {test_url}")
                driver.execute_script("window.open(arguments[0], '_blank');", test_url)
                time.sleep(2)
                
                # Переключаемся на новую вкладку
                if len(driver.window_handles) > 1:
                    driver.switch_to.window(driver.window_handles[-1])
                    print(f"[ЛОГ] ✓ Тестовая вкладка открыта")
                    time.sleep(1)
                    # Возвращаемся на главную вкладку
                    driver.switch_to.window(driver.window_handles[0])
                else:
                    print(f"[ЛОГ] ⚠ Вкладка не открылась, возможно браузер заблокировал")
            except Exception as e:
                print(f"[ЛОГ] ⚠ Ошибка открытия тестовой вкладки: {e}")
            
            try:
                input(f"\n⏸ Нажмите ENTER после того как разрешите открытие вкладок в браузере...")
            except KeyboardInterrupt:
                print(f"\n[!] Прервано пользователем")
                driver.quit()
                return
            
            # Закрываем тестовую вкладку если она открыта
            try:
                if len(driver.window_handles) > 1:
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    print(f"[ЛОГ] ✓ Тестовая вкладка закрыта")
            except:
                pass
        
        # Парсинг
        print(f"\n[2/3] Парсинг цен для {len(MISSING_ARTICLES)} артикулов...")
        results = process_articles_parallel(driver, MISSING_ARTICLES)
        
        print(f"\n✓ Парсинг завершен: собрано {len(results)} товаров")
        
    except Exception as e:
        print(f"\n[!] КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Сохраняем результаты
        print(f"\n{'='*80}")
        print("СОХРАНЕНИЕ РЕЗУЛЬТАТОВ")
        print(f"{'='*80}")
        
        if len(results) > 0:
            if save_results_to_excel(results, OUTPUT_EXCEL_FILE):
                print(f"✓ Данные сохранены в Excel файл")
            else:
                print(f"⚠ Не удалось сохранить в Excel")
        else:
            print(f"\n⚠ Нет данных для сохранения")
        
        if driver:
            print(f"\n[Закрываю Chrome через 5 секунд...]")
            time.sleep(5)
            driver.quit()
    
    print(f"\n{'='*80}")
    print("ЗАВЕРШЕНО")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()

