# -*- coding: utf-8 -*-
"""
ТЕСТ: Парсинг цен WB через requests + BeautifulSoup
Имитирует человека, получает HTML и парсит цены
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import random

def parse_wb_product(nm_id):
    """
    Парсит карточку товара WB через запрос к странице
    Извлекает JSON из <script> тега
    """
    
    url = f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }
    
    try:
        print(f"\n[{nm_id}] Запрос к странице...")
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем JSON данные в скриптах
            scripts = soup.find_all('script')
            
            for script in scripts:
                if script.string and '__wb__plp_products' in script.string:
                    # Нашли данные товара!
                    print(f"  ✓ Найден JSON с данными")
                    
                    # Извлекаем JSON
                    script_text = script.string
                    start = script_text.find('{')
                    end = script_text.rfind('}') + 1
                    json_data = json.loads(script_text[start:end])
                    
                    # Парсим данные
                    result = extract_price_data(json_data, nm_id)
                    return result
            
            # Если JSON не найден, ищем в HTML
            print(f"  Пробуем парсить HTML...")
            result = parse_html_prices(soup, nm_id)
            return result
        
        else:
            print(f"  ✗ Ошибка {response.status_code}")
            return None
    
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
        return None


def extract_price_data(json_data, nm_id):
    """Извлекает цены из JSON данных"""
    try:
        # Структура может быть разной, ищем товар
        if 'products' in json_data:
            products = json_data['products']
            for product in products:
                if str(product.get('id')) == str(nm_id):
                    return parse_product_json(product)
        
        return None
    except:
        return None


def parse_product_json(product):
    """Парсит JSON объект товара"""
    try:
        name = product.get('name', '')
        
        # Цены в копейках
        price_u = product.get('priceU', 0) / 100
        sale_price_u = product.get('salePriceU', 0) / 100
        
        # Расширенные данные
        extended = product.get('extended', {})
        basic_price = extended.get('basicPriceU', price_u * 100) / 100
        
        # Скидки
        sale = product.get('sale', 0)
        
        return {
            'name': name,
            'price': basic_price,
            'sale_price': sale_price_u,
            'discount': sale,
            'source': 'JSON'
        }
    except:
        return None


def parse_html_prices(soup, nm_id):
    """Парсит цены напрямую из HTML"""
    try:
        result = {
            'name': '',
            'price': 0,
            'sale_price': 0,
            'discount': 0,
            'source': 'HTML'
        }
        
        # Ищем название
        title_elem = soup.find('h1', class_=lambda x: x and 'product-page__title' in x)
        if title_elem:
            result['name'] = title_elem.get_text(strip=True)
        
        # Ищем цены (разные варианты селекторов)
        price_selectors = [
            {'class': 'price-block__final-price'},
            {'class': lambda x: x and 'final-price' in x},
            {'class': lambda x: x and 'wallet-price' in x}
        ]
        
        for selector in price_selectors:
            price_elem = soup.find('span', selector)
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                # Извлекаем число
                price = ''.join(c for c in price_text if c.isdigit() or c == ' ')
                price = price.replace(' ', '')
                if price:
                    result['sale_price'] = int(price)
                    break
        
        # Ищем старую цену
        old_price_selectors = [
            {'class': 'price-block__old-price'},
            {'class': lambda x: x and 'old-price' in x}
        ]
        
        for selector in old_price_selectors:
            old_price_elem = soup.find('del', selector) or soup.find('span', selector)
            if old_price_elem:
                old_price_text = old_price_elem.get_text(strip=True)
                price = ''.join(c for c in old_price_text if c.isdigit() or c == ' ')
                price = price.replace(' ', '')
                if price:
                    result['price'] = int(price)
                    break
        
        # Ищем процент скидки
        discount_selectors = [
            {'class': 'price-block__sale-percent'},
            {'class': lambda x: x and 'percent' in x}
        ]
        
        for selector in discount_selectors:
            discount_elem = soup.find('span', selector)
            if discount_elem:
                discount_text = discount_elem.get_text(strip=True)
                discount = ''.join(c for c in discount_text if c.isdigit())
                if discount:
                    result['discount'] = int(discount)
                    break
        
        return result if result['name'] or result['sale_price'] > 0 else None
    
    except Exception as e:
        print(f"  Ошибка парсинга HTML: {e}")
        return None


# Тест на 3 артикулах
if __name__ == "__main__":
    test_ids = [583658258, 214690928, 242175842]
    
    print("="*60)
    print("ТЕСТ: Парсинг через requests")
    print("="*60)
    
    for nm_id in test_ids:
        result = parse_wb_product(nm_id)
        
        if result:
            print(f"\n  ✓ УСПЕХ:")
            print(f"    Название: {result.get('name', 'N/A')}")
            print(f"    Базовая цена: {result.get('price', 0)} ₽")
            print(f"    Цена со скидкой: {result.get('sale_price', 0)} ₽")
            print(f"    Скидка: {result.get('discount', 0)}%")
            print(f"    Источник: {result.get('source', 'N/A')}")
        else:
            print(f"\n  ✗ НЕ УДАЛОСЬ СПАРСИТЬ")
        
        # Задержка как человек (2-5 секунд)
        delay = random.uniform(2, 5)
        print(f"\n  [пауза {delay:.1f}с]")
        time.sleep(delay)
    
    print("\n" + "="*60)
    print("ТЕСТ ЗАВЕРШЁН")
    print("="*60)



