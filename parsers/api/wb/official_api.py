# -*- coding: utf-8 -*-
"""
Работа с официальным API Wildberries
Использует существующий код из Parser_WB_API_FAST.py
"""

import os
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# API эндпоинты
WB_PRICES_API_URL = "https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter"
WB_CONTENT_API_URL = "https://content-api.wildberries.ru/content/v2/get/cards/list"

# Названия кабинетов
CABINET_NAMES = ["COSMO", "MMA", "MAB", "MAU", "DREAMLAB", "BEAUTYLAB"]


class WBOfficialAPI:
    """Работа с официальным API Wildberries"""
    
    def __init__(self, api_keys: Optional[List[str]] = None):
        """
        Инициализация API клиента
        
        Args:
            api_keys: Список API ключей. Если не указан, загружает из .env
        """
        if api_keys is None:
            api_keys = self.load_api_keys_from_env()
        
        self.api_keys = api_keys
    
    def load_api_keys_from_env(self) -> List[str]:
        """Загружает API ключи из .env файла"""
        load_dotenv()
        
        api_keys = []
        for cabinet_name in CABINET_NAMES:
            api_key = os.getenv(cabinet_name, "").strip()
            if api_key:
                api_keys.append(api_key)
        
        print(f"[API] Загружено {len(api_keys)} API ключей из .env")
        return api_keys
    
    def get_prices(self, articles: List[str], api_key: Optional[str] = None) -> Dict[str, Dict]:
        """
        Получает цены через официальный API
        
        Args:
            articles: Список артикулов (nmID)
            api_key: API ключ. Если не указан, использует первый из списка
        
        Returns:
            Словарь {артикул: {price, discountedPrice, clubDiscountedPrice, ...}}
        """
        if not api_key:
            if not self.api_keys:
                print("[ERROR] API ключи не найдены!")
                return {}
            api_key = self.api_keys[0]
        
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
        
        prices_info = {}
        
        # Обрабатываем батчами по 1000
        batch_size = 1000
        nm_ids = [int(art) for art in articles if str(art).isdigit()]
        
        for i in range(0, len(nm_ids), batch_size):
            batch = nm_ids[i:i + batch_size]
            
            payload = {
                "limit": 1000,
                "offset": 0,
                "nmList": batch
            }
            
            try:
                response = requests.post(WB_PRICES_API_URL, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Парсим товары
                    goods_list = []
                    if "data" in data and "listGoods" in data["data"]:
                        goods_list = data["data"]["listGoods"]
                    elif "listGoods" in data:
                        goods_list = data["listGoods"]
                    
                    # Обрабатываем товары
                    for item in goods_list:
                        nm_id = str(item.get("nmID", ""))
                        
                        sizes = item.get("sizes", [])
                        if sizes and len(sizes) > 0:
                            size_data = sizes[0]
                            
                            prices_info[nm_id] = {
                                "price": float(size_data.get("price", 0)),
                                "discountedPrice": float(size_data.get("discountedPrice", 0)),
                                "clubDiscountedPrice": float(size_data.get("clubDiscountedPrice", 0)),
                                "discount": float(item.get("discount", 0)),
                                "clubDiscount": float(item.get("clubDiscount", 0))
                            }
                    
                    print(f"  Батч {i//batch_size + 1}: загружено цен для {len(goods_list)} товаров")
                
                else:
                    print(f"  [ERROR] Ошибка API: {response.status_code}")
                    if response.status_code == 401:
                        print("  [ERROR] Неверный API ключ!")
                        break
            
            except Exception as e:
                print(f"  [ERROR] Ошибка запроса: {e}")
                continue
        
        return prices_info
    
    def get_product_info(self, articles: List[str], api_key: Optional[str] = None) -> Dict[str, Dict]:
        """
        Получает информацию о товарах (названия, артикулы)
        
        Args:
            articles: Список артикулов
            api_key: API ключ
        
        Returns:
            Словарь {артикул: {name, nmID, vendorCode, ...}}
        """
        if not api_key:
            if not self.api_keys:
                return {}
            api_key = self.api_keys[0]
        
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
        
        product_info = {}
        
        # Content API работает с пагинацией
        cursor_updatedAt = ""
        cursor_nmID = 0
        
        while True:
            payload = {
                "settings": {
                    "cursor": {
                        "updatedAt": cursor_updatedAt,
                        "nmID": cursor_nmID
                    },
                    "filter": {
                        "withPhoto": -1
                    },
                    "limit": 100
                }
            }
            
            try:
                response = requests.post(WB_CONTENT_API_URL, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    cards = data.get("data", {}).get("cards", [])
                    if not cards:
                        break
                    
                    for card in cards:
                        nm_id = str(card.get("nmID", ""))
                        if nm_id in articles:
                            product_info[nm_id] = {
                                "name": card.get("imtName", ""),
                                "nmID": nm_id,
                                "vendorCode": card.get("vendorCode", ""),
                                "brand": card.get("brand", "")
                            }
                    
                    # Обновляем курсор для следующей страницы
                    if cards:
                        last_card = cards[-1]
                        cursor_updatedAt = last_card.get("updatedAt", "")
                        cursor_nmID = last_card.get("nmID", 0)
                    else:
                        break
                
                else:
                    print(f"[ERROR] Ошибка Content API: {response.status_code}")
                    break
            
            except Exception as e:
                print(f"[ERROR] Ошибка запроса: {e}")
                break
        
        return product_info

















