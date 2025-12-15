# -*- coding: utf-8 -*-
"""
ПАРСЕР ЦЕН WILDBERRIES - ГИБРИДНЫЙ МЕТОД (ПОЛНЫЕ ДАННЫЕ)
Комбинирует XPATH метод (быстрый сбор ссылок) + открытие карточек (все цены)

ЧТО СОБИРАЕТ:
- Артикул
- Название товара
- Ссылка на товар
- Цена ДО СПП (старая зачеркнутая)
- Цена ПОСЛЕ СПП (текущая без карты)
- Цена С КАРТОЙ (финальная с картой WB)

ПРЕИМУЩЕСТВА:
- Получает ВСЕ 3 типа цен (в отличие от XPATH метода)
- Быстрее старого метода (сначала собирает ссылки быстро)
- Можно анализировать скидки СПП и выгоду от карты

АЛГОРИТМ:
ФАЗА 1: Быстрый сбор ссылок (XPATH метод)
  1. Открывает страницу продавца
  2. Скроллит до конца
  3. Извлекает артикулы, названия, ссылки (100 товаров за раз)
  4. Переходит на следующую страницу

ФАЗА 2: Сбор всех цен (открытие карточек)
  1. Для каждой ссылки открывает карточку товара
  2. Извлекает цену ДО СПП
  3. Извлекает цену ПОСЛЕ СПП
  4. Извлекает цену С КАРТОЙ
  5. Закрывает карточку

ВРЕМЯ: ~5-7 минут на 450 товаров (vs 10 минут старым методом)
"""

import os
import time
import random
import re
import subprocess
import shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc
from openpyxl import Workbook
from lxml import html

# ================================
# КОНФИГУРАЦИЯ
# ================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Список страниц продавцов/брендов для парсинга
SELLER_URLS = [
    "https://www.wildberries.ru/brands/68941-likato-professional",
    "https://www.wildberries.ru/seller/224650",
    # Добавьте сюда ссылки на страницы других кабинетов
]

# Выходной файл
OUTPUT_EXCEL_FILE = os.path.join(DATA_DIR, "prices_hybrid_results.xlsx")

# Настройки браузера
USE_TEMP_PROFILE = True
TEMP_PROFILE_DIR = os.path.join(PROJECT_ROOT, "chrome_parser_profile")
HEADLESS_MODE = False

# Копировать профиль из основного Chrome
COPY_PROFILE_DATA = True
CHROME_USER_DATA_DIR = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
SOURCE_PROFILE_FOR_COPY = "Profile 4"

# Настройки парсинга
SCROLL_PAUSE_TIME = 2.0
MAX_SCROLL_ATTEMPTS = 30
PAGE_LOAD_TIMEOUT = 10
SCROLL_STEP = 500

# Тестовый режим
TEST_MODE = False  # True = первая страница, False = все страницы
MAX_PAGES = 10

# Параллельная обработка карточек (ФАЗА 2)
PARALLEL_TABS = 5  # Количество параллельных вкладок для открытия карточек
DELAY_BETWEEN_BATCHES = (0.5, 1.0)  # Задержка между пакетами карточек

# Промежуточное сохранение
SAVE_INTERMEDIATE_RESULTS = True
SAVE_EVERY_N_PRODUCTS = 20


# ================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ================================

def cleanup_profile_locks(profile_path):
    """Очищает lock-файлы профиля Chrome"""
    lock_files = ["SingletonLock", "lockfile", "SingletonSocket", "SingletonCookie", "DevToolsActivePort"]
    for lock_file in lock_files:
        lock_path = os.path.join(profile_path, lock_file)
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except:
                pass


def copy_profile_data(source_profile, target_profile):
    """Копирует cookies и данные авторизации из профиля Chrome"""
    print(f"\n{'='*60}")
    print(f"[КОПИРОВАНИЕ] Перенос данных профиля")
    print(f"{'='*60}")
    print(f"[ЛОГ] Источник: {source_profile}")
    print(f"[ЛОГ] Назначение: {target_profile}")
    
    if not os.path.exists(source_profile):
        print(f"[!] ОШИБКА: Исходный профиль не найден!")
        return False
    
    if not os.path.exists(target_profile):
        os.makedirs(target_profile, exist_ok=True)
    
    files_to_copy = [
        "Cookies", "Cookies-journal",
        "Network\\Cookies", "Network\\Cookies-journal",
        "Login Data", "Login Data-journal",
        "Local Storage", "Session Storage", "IndexedDB",
        "Preferences", "Web Data", "Web Data-journal"
    ]
    
    copied_count = 0
    for file_name in files_to_copy:
        source_file = os.path.join(source_profile, file_name)
        target_file = os.path.join(target_profile, file_name)
        
        if os.path.exists(source_file):
            try:
                target_dir = os.path.dirname(target_file)
                if target_dir and not os.path.exists(target_dir):
                    os.makedirs(target_dir, exist_ok=True)
                
                if os.path.isdir(source_file):
                    if os.path.exists(target_file):
                        shutil.rmtree(target_file)
                    shutil.copytree(source_file, target_file)
                    print(f"[ЛОГ] ✓ Скопирована директория: {file_name}")
                else:
                    shutil.copy2(source_file, target_file)
                    print(f"[ЛОГ] ✓ Скопирован файл: {file_name}")
                
                copied_count += 1
            except Exception as e:
                print(f"[ЛОГ] ✗ Ошибка копирования {file_name}: {e}")
    
    print(f"\n[ЛОГ] Итого скопировано: {copied_count} элементов")
    print(f"{'='*60}\n")
    return copied_count > 0


def check_chrome_running():
    """Проверяет, запущен ли Chrome"""
    try:
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                              capture_output=True, text=True, timeout=5)
        is_running = 'chrome.exe' in result.stdout
        if is_running:
            lines = [line for line in result.stdout.split('\n') if 'chrome.exe' in line]
            print(f"[ЛОГ] ⚠ Chrome уже запущен (процессов: {len(lines)})")
        return is_running
    except:
        return False


def setup_browser():
    """Настраивает и запускает браузер"""
    print(f"\n{'='*60}")
    print(f"[БРАУЗЕР] Настройка Chrome")
    print(f"{'='*60}")
    
    chrome_running = check_chrome_running()
    if chrome_running:
        print(f"[ЛОГ] ⚠ Обнаружен запущенный Chrome")
        print(f"[ЛОГ] Рекомендуется закрыть Chrome перед запуском парсера")
        print(f"[ЛОГ] Продолжаю попытку запуска...")
        time.sleep(2)
    
    if COPY_PROFILE_DATA and USE_TEMP_PROFILE:
        source_profile_path = os.path.join(CHROME_USER_DATA_DIR, SOURCE_PROFILE_FOR_COPY)
        if os.path.exists(source_profile_path):
            copy_profile_data(source_profile_path, TEMP_PROFILE_DIR)
            cleanup_profile_locks(TEMP_PROFILE_DIR)
            time.sleep(1)
    
    if USE_TEMP_PROFILE:
        print(f"[ЛОГ] Очистка lock-файлов профиля...")
        cleanup_profile_locks(TEMP_PROFILE_DIR)
        time.sleep(1)
    
    attempts = [
        {'use_subprocess': True, 'version_main': None},
        {'use_subprocess': True, 'version_main': 143},
        {'use_subprocess': False, 'version_main': None},
    ]
    
    for attempt_num, attempt_config in enumerate(attempts, 1):
        try:
            print(f"\n[ЛОГ] Попытка {attempt_num}/{len(attempts)} запуска Chrome...")
            
            if USE_TEMP_PROFILE:
                driver = uc.Chrome(
                    user_data_dir=TEMP_PROFILE_DIR,
                    headless=HEADLESS_MODE,
                    use_subprocess=attempt_config['use_subprocess'],
                    version_main=attempt_config['version_main']
                )
            else:
                driver = uc.Chrome(
                    headless=HEADLESS_MODE,
                    use_subprocess=attempt_config['use_subprocess'],
                    version_main=attempt_config['version_main']
                )
            
            print(f"[ЛОГ] ✓ Chrome запущен успешно!")
            
            try:
                driver.current_url
            except:
                print(f"[ЛОГ] ⚠ Драйвер создан, но не отвечает. Пробую следующую попытку...")
                try:
                    driver.quit()
                except:
                    pass
                continue
            
            driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            return driver
        
        except Exception as e:
            error_msg = str(e)
            print(f"[ЛОГ] ✗ Попытка {attempt_num} не удалась: {error_msg[:200]}")
            
            if attempt_num == len(attempts):
                print(f"\n{'='*60}")
                print(f"[ОШИБКА] Все попытки запуска Chrome не удались")
                print(f"{'='*60}")
                print(f"\n💡 ВОЗМОЖНЫЕ РЕШЕНИЯ:")
                print(f"   1. Закройте ВСЕ окна Chrome: taskkill /F /IM chrome.exe")
                print(f"   2. Подождите 10 секунд и попробуйте снова")
                print(f"   3. Перезагрузите компьютер")
            else:
                time.sleep(2)
    
    return None


def scroll_to_bottom(driver):
    """Скроллит страницу до конца для загрузки всех товаров"""
    print(f"\n[СКРОЛЛ] Загрузка всех товаров...")
    
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_count = 0
    no_change_count = 0
    
    while scroll_count < MAX_SCROLL_ATTEMPTS:
        current_position = driver.execute_script("return window.pageYOffset")
        target_position = current_position + SCROLL_STEP
        driver.execute_script(f"window.scrollTo(0, {target_position});")
        time.sleep(0.3)
        
        if scroll_count % 3 == 0:
            time.sleep(SCROLL_PAUSE_TIME)
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                no_change_count += 1
                if no_change_count >= 3:
                    print(f"[ЛОГ] ✓ Достигнут конец страницы (попыток скролла: {scroll_count + 1})")
                    break
            else:
                no_change_count = 0
                last_height = new_height
        
        scroll_count += 1
    
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    
    return scroll_count


def extract_article_from_url(url):
    """Извлекает артикул из URL товара"""
    match = re.search(r'/catalog/(\d+)/', url)
    if match:
        return match.group(1)
    return None


# ================================
# ФАЗА 1: БЫСТРЫЙ СБОР ССЫЛОК (XPATH)
# ================================

def parse_links_from_page(driver):
    """Извлекает ссылки на товары со страницы продавца"""
    print(f"\n[ФАЗА 1] Извлечение ссылок на товары...")
    
    page_source = driver.page_source
    tree = html.fromstring(page_source)
    
    products = []
    
    card_selectors = [
        "//article[contains(@class, 'product-card')]",
        "//div[contains(@class, 'product-card')]",
        "//div[@data-nm-id]",
        "//article[@id]",
        "//div[contains(@class, 'j-card-item')]",
    ]
    
    cards = []
    for selector in card_selectors:
        cards = tree.xpath(selector)
        if cards:
            print(f"[ЛОГ] Найдено карточек: {len(cards)} (селектор: {selector})")
            break
    
    if not cards:
        print(f"[!] Карточки товаров не найдены!")
        return []
    
    for idx, card in enumerate(cards, 1):
        try:
            article = None
            article = card.get('data-nm-id')
            
            if not article:
                links = card.xpath('.//a[contains(@href, "/catalog/")]/@href')
                if links:
                    article = extract_article_from_url(links[0])
            
            if not article:
                continue
            
            product_name = None
            product_url = None
            
            name_elements = card.xpath('.//a[@aria-label]/@aria-label')
            if name_elements:
                product_name = name_elements[0].strip()
            
            link_elements = card.xpath('.//a[contains(@class, "product-card__link")]/@href')
            if link_elements:
                product_url = link_elements[0]
                if not product_url.startswith('http'):
                    product_url = f"https://www.wildberries.ru{product_url}"
            
            if product_url:
                products.append({
                    'article': article,
                    'name': product_name or '',
                    'url': product_url,
                })
        
        except Exception as e:
            print(f"[ЛОГ] Ошибка парсинга карточки {idx}: {e}")
            continue
    
    print(f"[ЛОГ] ✓ Извлечено ссылок: {len(products)}")
    return products


def collect_all_links(driver, seller_url):
    """Собирает все ссылки со всех страниц продавца"""
    print(f"\n{'='*80}")
    print(f"[ФАЗА 1] СБОР ССЫЛОК: {seller_url}")
    print(f"{'='*80}")
    
    all_links = []
    page_num = 1
    
    try:
        driver.get(seller_url)
        time.sleep(3)
        
        if "Почти готово" in driver.title or "captcha" in driver.page_source.lower():
            print(f"\n[!] CAPTCHA обнаружена!")
            print(f"    Подожди 30 секунд и реши капчу вручную...")
            time.sleep(30)
        
        while page_num <= MAX_PAGES:
            print(f"\n[СТРАНИЦА {page_num}]")
            
            scroll_to_bottom(driver)
            
            links = parse_links_from_page(driver)
            
            if not links:
                print(f"[!] Ссылки не найдены на странице {page_num}")
                break
            
            all_links.extend(links)
            print(f"[ЛОГ] ✓ Собрано ссылок со страницы: {len(links)}")
            print(f"[ЛОГ] ✓ Всего собрано: {len(all_links)}")
            
            if TEST_MODE:
                print(f"\n[ТЕСТ] Остановка после первой страницы")
                break
            
            if not find_next_page_button(driver):
                print(f"[ЛОГ] Достигнута последняя страница")
                break
            
            page_num += 1
    
    except Exception as e:
        print(f"\n[!] ОШИБКА при сборе ссылок: {e}")
        import traceback
        traceback.print_exc()
    
    return all_links


def find_next_page_button(driver):
    """Ищет кнопку 'Следующая страница'"""
    try:
        next_button_selectors = [
            "//a[contains(@class, 'pagination-next')]",
            "//button[contains(@class, 'pagination-next')]",
            "//a[contains(text(), 'Следующая')]",
            "//button[contains(text(), 'Следующая')]",
            "//a[@rel='next']",
        ]
        
        for selector in next_button_selectors:
            try:
                button = driver.find_element(By.XPATH, selector)
                if button.is_displayed() and button.is_enabled():
                    print(f"[ЛОГ] Найдена кнопка 'Следующая страница'")
                    button.click()
                    time.sleep(2)
                    return True
            except:
                continue
        
        return False
    
    except Exception as e:
        print(f"[ЛОГ] Ошибка поиска кнопки пагинации: {e}")
        return False


# ================================
# ФАЗА 2: СБОР ВСЕХ ЦЕН (КАРТОЧКИ)
# ================================

def parse_all_prices_from_card(driver, article, url):
    """
    Извлекает все 3 типа цен с карточки товара
    Возвращает: (цена_до_спп, цена_после_спп, цена_с_картой)
    """
    try:
        # Проверяем на captcha
        if "Почти готово" in driver.title or "captcha" in driver.page_source.lower():
            print(f"  [{article}] ⚠ Captcha обнаружена!")
            return (None, None, None)
        
        # Проверяем наличие товара
        try:
            sold_out_element = driver.find_element(By.CSS_SELECTOR, "h2[class*='soldOutProduct']")
            print(f"  [{article}] ⚠ Товар недоступен")
            return (0, 0, 0)
        except:
            pass
        
        page_text = driver.page_source.lower()
        unavailable_keywords = ['нет в наличии', 'товар недоступен', 'недоступен для заказа']
        for keyword in unavailable_keywords:
            if keyword in page_text:
                print(f"  [{article}] ⚠ Товар недоступен: '{keyword}'")
                return (0, 0, 0)
        
        # Кликаем на кнопку кошелька для показа всех цен
        try:
            wallet_button = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[class*='priceBlockWalletPrice']"))
            )
            wallet_button.click()
            time.sleep(0.5)
        except:
            pass
        
        # ЦЕНА ДО СПП (старая зачеркнутая)
        price_before_spp = None
        old_price_selectors = [
            (By.CSS_SELECTOR, "del.price-block__old-price"),
            (By.CSS_SELECTOR, "del[class*='old-price']"),
            (By.CSS_SELECTOR, "s.price-block__old-price"),
            (By.CSS_SELECTOR, "span[class*='old-price']"),
        ]
        for by, selector in old_price_selectors:
            try:
                elem = driver.find_element(by, selector)
                price_text = elem.text.strip()
                price_num = re.sub(r'[^\d]', '', price_text)
                if price_num:
                    price_before_spp = int(price_num)
                    break
            except:
                continue
        
        # ЦЕНА ПОСЛЕ СПП (текущая без карты)
        price_after_spp = None
        current_price_selectors = [
            (By.CSS_SELECTOR, "ins.price-block__final-price"),
            (By.CSS_SELECTOR, "ins[class*='final-price']"),
            (By.CSS_SELECTOR, "span[class*='final-price']"),
            (By.CSS_SELECTOR, "h2.mo-typography_color_primary"),
        ]
        for by, selector in current_price_selectors:
            try:
                elem = driver.find_element(by, selector)
                price_text = elem.text.strip()
                price_num = re.sub(r'[^\d]', '', price_text)
                if price_num:
                    price_after_spp = int(price_num)
                    break
            except:
                continue
        
        # ЦЕНА С КАРТОЙ (финальная)
        price_with_card = None
        card_price_selectors = [
            (By.CSS_SELECTOR, "h2.mo-typography_color_primary"),
            (By.CSS_SELECTOR, "span[class*='wallet-price']"),
            (By.CSS_SELECTOR, "ins[class*='wallet']"),
        ]
        for by, selector in card_price_selectors:
            try:
                elem = driver.find_element(by, selector)
                price_text = elem.text.strip()
                price_num = re.sub(r'[^\d]', '', price_text)
                if price_num:
                    price_with_card = int(price_num)
                    break
            except:
                continue
        
        # Если цена с картой не найдена, используем цену после СПП
        if not price_with_card and price_after_spp:
            price_with_card = price_after_spp
        
        return (price_before_spp or 0, price_after_spp or 0, price_with_card or 0)
    
    except Exception as e:
        print(f"  [{article}] ✗ Ошибка парсинга цен: {e}")
        return (0, 0, 0)


def process_cards_parallel(driver, products):
    """Обрабатывает карточки товаров параллельно"""
    print(f"\n{'='*80}")
    print(f"[ФАЗА 2] СБОР ВСЕХ ЦЕН: {len(products)} товаров")
    print(f"{'='*80}")
    print(f"[ЛОГ] Параллельных вкладок: {PARALLEL_TABS}")
    
    results = []
    main_window = driver.window_handles[0]
    total = len(products)
    
    for batch_start in range(0, total, PARALLEL_TABS):
        batch = products[batch_start : batch_start + PARALLEL_TABS]
        batch_num = batch_start // PARALLEL_TABS + 1
        total_batches = (total + PARALLEL_TABS - 1) // PARALLEL_TABS
        
        print(f"\n{'─'*80}")
        print(f"📦 ПАКЕТ {batch_num}/{total_batches} ({len(batch)} товаров)")
        print(f"{'─'*80}")
        
        # Открываем все вкладки пакета
        print(f"\n[1/3] Открываю {len(batch)} вкладок...")
        for idx, product in enumerate(batch):
            print(f"  [{batch_start + idx + 1}/{total}] Открываю: {product['article']}")
            driver.execute_script("window.open(arguments[0], '_blank');", product['url'])
            time.sleep(0.3)
        
        # Ждем загрузки
        print(f"\n[2/3] Жду загрузки страниц...")
        tabs = driver.window_handles[1:]
        time.sleep(2)
        
        # Парсим цены
        print(f"\n[3/3] Парсинг цен...")
        for idx, (tab_handle, product) in enumerate(zip(tabs, batch)):
            try:
                driver.switch_to.window(tab_handle)
                price_before, price_after, price_card = parse_all_prices_from_card(
                    driver, product['article'], product['url']
                )
                
                results.append({
                    'article': product['article'],
                    'name': product['name'],
                    'url': product['url'],
                    'price_before_spp': price_before,
                    'price_after_spp': price_after,
                    'price_with_card': price_card,
                })
                
                print(f"  [{batch_start + idx + 1}/{total}] {product['article']}: "
                      f"до СПП={price_before}₽, после СПП={price_after}₽, с картой={price_card}₽")
            
            except Exception as e:
                print(f"  [{batch_start + idx + 1}/{total}] {product['article']}: ✗ ошибка - {e}")
                results.append({
                    'article': product['article'],
                    'name': product['name'],
                    'url': product['url'],
                    'price_before_spp': 0,
                    'price_after_spp': 0,
                    'price_with_card': 0,
                })
        
        # Закрываем вкладки
        print(f"\n[4/4] Закрываю вкладки...")
        for tab_handle in tabs:
            try:
                driver.switch_to.window(tab_handle)
                driver.close()
            except:
                pass
        
        driver.switch_to.window(main_window)
        
        # Промежуточное сохранение
        if SAVE_INTERMEDIATE_RESULTS and len(results) % SAVE_EVERY_N_PRODUCTS == 0:
            print(f"\n💾 Промежуточное сохранение ({len(results)} товаров)...")
            save_to_excel(results, OUTPUT_EXCEL_FILE)
        
        # Задержка между пакетами
        if batch_start + PARALLEL_TABS < total:
            delay = random.uniform(*DELAY_BETWEEN_BATCHES)
            print(f"\n⏸ Пауза {delay:.1f}с перед следующим пакетом...\n")
            time.sleep(delay)
    
    return results


# ================================
# СОХРАНЕНИЕ РЕЗУЛЬТАТОВ
# ================================

def save_to_excel(results, output_file):
    """Сохраняет результаты в Excel"""
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Цены WB"
        
        ws.append([
            "Артикул",
            "Название товара",
            "Ссылка на товар",
            "Цена ДО СПП (₽)",
            "Цена ПОСЛЕ СПП (₽)",
            "Цена С КАРТОЙ (₽)"
        ])
        
        for result in results:
            ws.append([
                result['article'],
                result['name'],
                result['url'],
                result['price_before_spp'],
                result['price_after_spp'],
                result['price_with_card']
            ])
        
        ws.auto_filter.ref = ws.dimensions
        wb.save(output_file)
        wb.close()
        
        print(f"[ЛОГ] ✓ Файл сохранен: {output_file}")
        return True
    
    except Exception as e:
        print(f"[!] ОШИБКА сохранения: {e}")
        return False


# ================================
# ГЛАВНАЯ ФУНКЦИЯ
# ================================

def main():
    print("\n" + "="*80)
    print("ПАРСЕР ЦЕН WB - ГИБРИДНЫЙ МЕТОД (ПОЛНЫЕ ДАННЫЕ)")
    print("="*80)
    print(f"\n[РЕЖИМ] {'ТЕСТ (первая страница)' if TEST_MODE else 'ПОЛНЫЙ (все страницы)'}")
    print(f"[ПРОДАВЦОВ] {len(SELLER_URLS)}")
    print(f"[ВЫХОДНОЙ ФАЙЛ] {OUTPUT_EXCEL_FILE}")
    print(f"\n[АЛГОРИТМ]")
    print(f"  ФАЗА 1: Быстрый сбор ссылок со страниц продавца (XPATH)")
    print(f"  ФАЗА 2: Открытие карточек и сбор всех 3 типов цен")
    
    driver = setup_browser()
    if not driver:
        print("\n[!] Не удалось запустить браузер!")
        return
    
    all_results = []
    
    try:
        # ФАЗА 1: Собираем все ссылки
        print(f"\n{'='*80}")
        print(f"[ФАЗА 1] СБОР ССЫЛОК")
        print(f"{'='*80}")
        
        all_links = []
        for idx, seller_url in enumerate(SELLER_URLS, 1):
            print(f"\n[ПРОДАВЕЦ {idx}/{len(SELLER_URLS)}]")
            links = collect_all_links(driver, seller_url)
            all_links.extend(links)
            print(f"[ЛОГ] ✓ Собрано ссылок с этого продавца: {len(links)}")
            
            if idx < len(SELLER_URLS):
                delay = random.uniform(2, 4)
                print(f"[ЛОГ] Пауза {delay:.1f}с перед следующим продавцом...")
                time.sleep(delay)
        
        print(f"\n{'='*80}")
        print(f"[ФАЗА 1 ЗАВЕРШЕНА] Всего собрано ссылок: {len(all_links)}")
        print(f"{'='*80}")
        
        if not all_links:
            print(f"\n[!] Нет ссылок для обработки!")
            return
        
        # ФАЗА 2: Собираем все цены
        print(f"\n{'='*80}")
        print(f"[ФАЗА 2] СБОР ВСЕХ ЦЕН")
        print(f"{'='*80}")
        
        all_results = process_cards_parallel(driver, all_links)
        
        print(f"\n{'='*80}")
        print(f"[ИТОГО] Обработано товаров: {len(all_results)}")
        print(f"{'='*80}")
        
        if all_results:
            save_to_excel(all_results, OUTPUT_EXCEL_FILE)
        else:
            print(f"\n[!] Нет данных для сохранения!")
    
    except Exception as e:
        print(f"\n[!] КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print(f"\n[ЛОГ] Закрытие браузера...")
        time.sleep(2)
        driver.quit()
    
    print(f"\n{'='*80}")
    print("ЗАВЕРШЕНО")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()



