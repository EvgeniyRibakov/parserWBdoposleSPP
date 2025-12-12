# -*- coding: utf-8 -*-
"""
ПАРСЕР ЦЕН WILDBERRIES - XPATH МЕТОД (БЫСТРЫЙ)
Парсит данные со страницы продавца/бренда (100 товаров за раз)

ЧТО СОБИРАЕТ:
- Артикул
- Название товара
- Ссылка на товар
- Цена с картой WB (финальная цена после всех скидок)

⚠️ ВАЖНО: На странице продавца WB показывает ТОЛЬКО цену с картой!
Цены ДО СПП и ПОСЛЕ СПП (без карты) на странице продавца НЕТ.

Для получения всех 3 типов цен есть 2 варианта:
1. Использовать старый метод (Parser_WB_Search.py) - медленнее, но все цены
2. Гибридный: собрать ссылки здесь, потом открыть карточки для остальных цен

ПРЕИМУЩЕСТВА:
- 10-20x быстрее старого метода
- Получает артикулы, названия, ссылки за считанные минуты
- Меньше нагрузка на WB = меньше риск блокировки
- Можно парсить несколько кабинетов параллельно

ПРИНЦИП РАБОТЫ:
1. Открывает страницу продавца/бренда (https://www.wildberries.ru/seller/ID)
2. Скроллит до конца для загрузки всех товаров (lazy loading)
3. Извлекает данные через XPath селекторы:
   - Артикул (из ссылки на товар)
   - Название (из aria-label)
   - Ссылка (href карточки)
   - Цена с картой (ins.price__lower-price.wallet-price)
4. Переходит на следующую страницу (пагинация)
5. Сохраняет результаты в Excel

НАСТРОЙКА:
- Укажите SELLER_URLS - список страниц продавцов/брендов
- Можно добавить несколько URL для разных кабинетов
"""

import os
import time
import random
import re
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
OUTPUT_EXCEL_FILE = os.path.join(DATA_DIR, "prices_xpath_results.xlsx")

# Настройки браузера
USE_TEMP_PROFILE = True
TEMP_PROFILE_DIR = os.path.join(PROJECT_ROOT, "chrome_parser_profile")
HEADLESS_MODE = False  # True = фоновый режим (НЕ рекомендуется для первого запуска)

# Копировать профиль из основного Chrome
COPY_PROFILE_DATA = True
CHROME_USER_DATA_DIR = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
SOURCE_PROFILE_FOR_COPY = "Profile 4"  # Откуда копировать cookies/авторизацию

# Настройки парсинга
SCROLL_PAUSE_TIME = 2.0  # Задержка после скролла (для загрузки товаров)
MAX_SCROLL_ATTEMPTS = 30  # Максимум попыток скролла
PAGE_LOAD_TIMEOUT = 10  # Таймаут загрузки страницы
SCROLL_STEP = 500  # Пикселей за один скролл (меньше = плавнее)

# Тестовый режим
TEST_MODE = False  # True = первая страница, False = все страницы
MAX_PAGES = 10  # Максимум страниц для парсинга (защита от бесконечного цикла)

# Debug режим
DEBUG_MODE = True  # True = сохраняет HTML для анализа, выводит подробные логи


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
    import shutil
    
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
    
    # Файлы для копирования
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


def setup_browser():
    """Настраивает и запускает браузер"""
    print(f"\n{'='*60}")
    print(f"[БРАУЗЕР] Настройка Chrome")
    print(f"{'='*60}")
    
    # Копируем данные профиля если нужно
    if COPY_PROFILE_DATA and USE_TEMP_PROFILE:
        source_profile_path = os.path.join(CHROME_USER_DATA_DIR, SOURCE_PROFILE_FOR_COPY)
        if os.path.exists(source_profile_path):
            copy_profile_data(source_profile_path, TEMP_PROFILE_DIR)
            cleanup_profile_locks(TEMP_PROFILE_DIR)
            time.sleep(1)
    
    # Запускаем Chrome
    try:
        if USE_TEMP_PROFILE:
            print(f"[ЛОГ] Запуск Chrome с профилем: {TEMP_PROFILE_DIR}")
            driver = uc.Chrome(
                user_data_dir=TEMP_PROFILE_DIR,
                headless=HEADLESS_MODE,
                use_subprocess=True,
                version_main=143
            )
        else:
            print(f"[ЛОГ] Запуск Chrome с временным профилем")
            driver = uc.Chrome(
                headless=HEADLESS_MODE,
                use_subprocess=True,
                version_main=143
            )
        
        print(f"[ЛОГ] ✓ Chrome запущен")
        
        # Устанавливаем таймаут загрузки страниц
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        
        return driver
    
    except Exception as e:
        print(f"\n[!] ОШИБКА запуска Chrome: {e}")
        return None


def scroll_to_bottom(driver):
    """
    Скроллит страницу до конца для загрузки всех товаров
    WB использует lazy loading - товары подгружаются при скролле
    """
    print(f"\n[СКРОЛЛ] Загрузка всех товаров...")
    
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_count = 0
    no_change_count = 0  # Счетчик попыток без изменений
    
    while scroll_count < MAX_SCROLL_ATTEMPTS:
        # Плавный скролл вниз (по частям)
        current_position = driver.execute_script("return window.pageYOffset")
        target_position = current_position + SCROLL_STEP
        driver.execute_script(f"window.scrollTo(0, {target_position});")
        time.sleep(0.3)  # Короткая пауза между шагами
        
        # Каждые 3 скролла проверяем высоту
        if scroll_count % 3 == 0:
            time.sleep(SCROLL_PAUSE_TIME)  # Даём время на подгрузку
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                no_change_count += 1
                # Если 3 раза подряд высота не изменилась - конец
                if no_change_count >= 3:
                    print(f"[ЛОГ] ✓ Достигнут конец страницы (попыток скролла: {scroll_count + 1})")
                    break
            else:
                no_change_count = 0  # Сброс счетчика
                last_height = new_height
                if DEBUG_MODE:
                    print(f"[ЛОГ] Скролл {scroll_count}/{MAX_SCROLL_ATTEMPTS}... (высота: {new_height}px)")
        
        scroll_count += 1
    
    # Финальный скролл в самый низ
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)  # Увеличенная пауза для финальной подгрузки
    
    return scroll_count


def extract_article_from_url(url):
    """Извлекает артикул из URL товара"""
    # Примеры URL:
    # https://www.wildberries.ru/catalog/123456789/detail.aspx
    # /catalog/123456789/detail.aspx
    match = re.search(r'/catalog/(\d+)/', url)
    if match:
        return match.group(1)
    return None


def parse_products_from_page(driver, debug_mode=False):
    """
    Извлекает данные о товарах со страницы
    Возвращает список словарей с артикулами и ценами
    """
    print(f"\n[ПАРСИНГ] Извлечение данных о товарах...")
    
    # Получаем HTML страницы
    page_source = driver.page_source
    tree = html.fromstring(page_source)
    
    # DEBUG: Сохраняем HTML для анализа
    if debug_mode:
        debug_file = os.path.join(DATA_DIR, "debug_page.html")
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(page_source)
        print(f"[DEBUG] HTML сохранен: {debug_file}")
    
    products = []
    
    # CSS СЕЛЕКТОРЫ для поиска карточек товаров на WB
    # Структура может меняться, поэтому пробуем несколько вариантов
    
    card_selectors = [
        "//article[contains(@class, 'product-card')]",  # Основной селектор для /seller/
        "//div[contains(@class, 'product-card')]",       # Альтернативный
        "//div[@data-nm-id]",  # Карточки с артикулом в атрибуте
        "//article[@id]",      # Для страниц брендов
        "//div[contains(@class, 'j-card-item')]",  # Еще один вариант
    ]
    
    cards = []
    for selector in card_selectors:
        cards = tree.xpath(selector)
        if cards:
            print(f"[ЛОГ] Найдено карточек: {len(cards)} (селектор: {selector})")
            break
    
    if not cards:
        print(f"[!] Карточки товаров не найдены!")
        print(f"[ЛОГ] Возможно, изменилась структура HTML или страница не загрузилась")
        return []
    
    # Парсим каждую карточку
    for idx, card in enumerate(cards, 1):
        try:
            # АРТИКУЛ - пробуем разные способы извлечения
            article = None
            
            # Способ 1: из атрибута data-nm-id
            article = card.get('data-nm-id')
            
            # Способ 2: из ссылки на товар
            if not article:
                links = card.xpath('.//a[contains(@href, "/catalog/")]/@href')
                if links:
                    article = extract_article_from_url(links[0])
            
            # ДОПОЛНИТЕЛЬНО: извлекаем название и ссылку
            product_name = None
            product_url = None
            
            # Название из aria-label
            name_elements = card.xpath('.//a[@aria-label]/@aria-label')
            if name_elements:
                product_name = name_elements[0].strip()
            
            # Ссылка на товар
            link_elements = card.xpath('.//a[contains(@class, "product-card__link")]/@href')
            if link_elements:
                product_url = link_elements[0]
                # Если ссылка относительная - делаем абсолютной
                if not product_url.startswith('http'):
                    product_url = f"https://www.wildberries.ru{product_url}"
            
            if not article:
                continue  # Пропускаем карточку без артикула
            
            # ЦЕНЫ - пробуем извлечь все три типа
            
            # DEBUG: сохраняем HTML первой карточки
            if DEBUG_MODE and idx == 1:
                card_html = html.tostring(card, encoding='unicode', pretty_print=True)
                debug_card_file = os.path.join(DATA_DIR, "debug_card.html")
                with open(debug_card_file, 'w', encoding='utf-8') as f:
                    f.write(card_html)
                print(f"[DEBUG] HTML первой карточки сохранен: {debug_card_file}")
            
            # Цена С КАРТОЙ (основная цена на странице продавца)
            # На странице продавца WB показывает ТОЛЬКО цену с картой:
            # <ins class="price__lower-price wallet-price red-price">437&nbsp;₽</ins>
            price_current_selectors = [
                './/ins[contains(@class, "price__lower-price")]//text()',  # ← ПРИОРИТЕТ 1
                './/ins[contains(@class, "wallet-price")]//text()',
                './/ins[contains(@class, "red-price")]//text()',
                './/ins//text()',  # Любой ins тег
                './/*[contains(@class, "price__lower")]//text()',
                './/*[contains(@class, "price-lower")]//text()',
            ]
            price_current = None
            for selector in price_current_selectors:
                texts = card.xpath(selector)
                if texts:
                    for text in texts:
                        price_text = text.strip()
                        price_num = re.sub(r'[^\d]', '', price_text)
                        if price_num and int(price_num) > 0:
                            price_current = int(price_num)
                            if DEBUG_MODE and idx <= 2:
                                print(f"[DEBUG] Цена с картой найдена: {price_current} (селектор: {selector})")
                            break
                    if price_current:
                        break
            
            # Если цена найдена - сохраняем товар
            if price_current:
                products.append({
                    'article': article,
                    'name': product_name or '',
                    'url': product_url or '',
                    'price_with_card': price_current,  # На странице продавца ТОЛЬКО эта цена
                })
                
                # Логирование для отладки (первые 5 товаров)
                if idx <= 5:
                    print(f"[ЛОГ] Товар {idx}: артикул={article}, название={product_name[:30] if product_name else 'N/A'}..., "
                          f"цена с картой={price_current}₽")
        
        except Exception as e:
            print(f"[ЛОГ] Ошибка парсинга карточки {idx}: {e}")
            continue
    
    print(f"[ЛОГ] ✓ Извлечено товаров: {len(products)}")
    return products


def find_next_page_button(driver):
    """
    Ищет кнопку "Следующая страница" и кликает по ней
    Возвращает True если кнопка найдена, False если это последняя страница
    """
    try:
        # CSS селекторы для кнопки пагинации
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
                    time.sleep(2)  # Ждем загрузки следующей страницы
                    return True
            except:
                continue
        
        # Если кнопка не найдена - это последняя страница
        return False
    
    except Exception as e:
        print(f"[ЛОГ] Ошибка поиска кнопки пагинации: {e}")
        return False


def parse_seller_page(driver, seller_url):
    """
    Парсит одну страницу продавца/бренда
    Обрабатывает все страницы пагинации
    Возвращает список товаров
    """
    print(f"\n{'='*80}")
    print(f"[ПАРСИНГ] Страница: {seller_url}")
    print(f"{'='*80}")
    
    all_products = []
    page_num = 1
    
    try:
        # Открываем страницу
        driver.get(seller_url)
        time.sleep(3)  # Ждем загрузки
        
        # Проверяем на captcha
        if "Почти готово" in driver.title or "captcha" in driver.page_source.lower():
            print(f"\n[!] CAPTCHA обнаружена!")
            print(f"    Подожди 30 секунд и реши капчу вручную...")
            time.sleep(30)
        
        while page_num <= MAX_PAGES:
            print(f"\n[СТРАНИЦА {page_num}]")
            
            # Скроллим до конца для загрузки всех товаров
            scroll_to_bottom(driver)
            
            # Парсим товары
            products = parse_products_from_page(driver, debug_mode=(DEBUG_MODE and page_num == 1))
            
            if not products:
                print(f"[!] Товары не найдены на странице {page_num}")
                break
            
            all_products.extend(products)
            print(f"[ЛОГ] ✓ Собрано товаров со страницы: {len(products)}")
            print(f"[ЛОГ] ✓ Всего собрано: {len(all_products)}")
            
            # Тестовый режим - только первая страница
            if TEST_MODE:
                print(f"\n[ТЕСТ] Остановка после первой страницы")
                break
            
            # Ищем кнопку следующей страницы
            if not find_next_page_button(driver):
                print(f"[ЛОГ] Достигнута последняя страница")
                break
            
            page_num += 1
    
    except Exception as e:
        print(f"\n[!] ОШИБКА при парсинге: {e}")
        import traceback
        traceback.print_exc()
    
    return all_products


def save_to_excel(all_results, output_file):
    """Сохраняет результаты в Excel"""
    print(f"\n{'='*80}")
    print(f"[СОХРАНЕНИЕ] Запись результатов в Excel")
    print(f"{'='*80}")
    
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Цены WB"
        
        # Заголовки
        ws.append([
            "Артикул",
            "Название товара",
            "Ссылка на товар",
            "Цена С КАРТОЙ (₽)",
            "URL продавца"
        ])
        
        # Примечание: На странице продавца WB показывает только цену с картой
        # Цены ДО СПП и ПОСЛЕ СПП (без карты) нужно собирать с карточек товаров
        
        # Данные
        for seller_url, products in all_results.items():
            for product in products:
                ws.append([
                    product['article'],
                    product['name'],
                    product['url'],
                    product['price_with_card'],
                    seller_url
                ])
        
        # Автофильтр
        ws.auto_filter.ref = ws.dimensions
        
        # Сохраняем
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
    print("ПАРСЕР ЦЕН WB - XPATH МЕТОД (БЫСТРЫЙ)")
    print("="*80)
    print(f"\n[РЕЖИМ] {'ТЕСТ (первая страница)' if TEST_MODE else 'ПОЛНЫЙ (все страницы)'}")
    print(f"[ПРОДАВЦОВ] {len(SELLER_URLS)}")
    print(f"[ВЫХОДНОЙ ФАЙЛ] {OUTPUT_EXCEL_FILE}")
    
    # Запускаем браузер
    driver = setup_browser()
    if not driver:
        print("\n[!] Не удалось запустить браузер!")
        return
    
    all_results = {}
    
    try:
        # Парсим каждую страницу продавца
        for idx, seller_url in enumerate(SELLER_URLS, 1):
            print(f"\n{'='*80}")
            print(f"[ПРОДАВЕЦ {idx}/{len(SELLER_URLS)}]")
            print(f"{'='*80}")
            
            products = parse_seller_page(driver, seller_url)
            all_results[seller_url] = products
            
            print(f"\n[ЛОГ] ✓ Собрано товаров с этого продавца: {len(products)}")
            
            # Пауза между продавцами
            if idx < len(SELLER_URLS):
                delay = random.uniform(2, 4)
                print(f"[ЛОГ] Пауза {delay:.1f}с перед следующим продавцом...")
                time.sleep(delay)
        
        # Сохраняем результаты
        total_products = sum(len(products) for products in all_results.values())
        print(f"\n{'='*80}")
        print(f"[ИТОГО] Собрано товаров: {total_products}")
        print(f"{'='*80}")
        
        if total_products > 0:
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

