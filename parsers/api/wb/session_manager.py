# -*- coding: utf-8 -*-
"""
Управление сессиями и cookies для WB API
Извлекает cookies из браузера или создает новую сессию
"""

import os
import json
import sqlite3
import shutil
from pathlib import Path
from typing import Dict, Optional
import requests


class WBSessionManager:
    """Управление сессиями для работы с WB API"""
    
    def __init__(self, chrome_profile_path: Optional[str] = None):
        """
        Инициализация менеджера сессий
        
        Args:
            chrome_profile_path: Путь к профилю Chrome (опционально)
        """
        self.chrome_profile_path = chrome_profile_path
        self.session = requests.Session()
        self.cookies = {}
    
    def load_cookies_from_chrome(self, profile_path: Optional[str] = None) -> Dict[str, str]:
        """
        Загружает cookies из профиля Chrome
        
        Args:
            profile_path: Путь к профилю Chrome. Если не указан, использует self.chrome_profile_path
        
        Returns:
            Словарь с cookies
        """
        if not profile_path:
            profile_path = self.chrome_profile_path
        
        if not profile_path or not os.path.exists(profile_path):
            print("[WARNING] Профиль Chrome не найден, используем пустые cookies")
            return {}
        
        cookies_path = os.path.join(profile_path, "Network", "Cookies")
        
        if not os.path.exists(cookies_path):
            print(f"[WARNING] Файл cookies не найден: {cookies_path}")
            return {}
        
        try:
            # Копируем файл cookies для чтения (Chrome может блокировать оригинал)
            temp_cookies = cookies_path + ".temp"
            shutil.copy2(cookies_path, temp_cookies)
            
            conn = sqlite3.connect(temp_cookies)
            cursor = conn.cursor()
            
            # Получаем cookies для wildberries.ru
            cursor.execute("""
                SELECT name, value, host_key, path, expires_utc, is_secure
                FROM cookies
                WHERE host_key LIKE '%wildberries%' OR host_key LIKE '%wb%'
            """)
            
            cookies_dict = {}
            for row in cursor.fetchall():
                name, value, host_key, path, expires_utc, is_secure = row
                # Проверяем, не истекла ли cookie
                if expires_utc and expires_utc > 0:
                    # expires_utc в формате Windows (микросекунды с 1601-01-01)
                    # Конвертируем в Unix timestamp
                    expires_unix = (expires_utc / 1000000) - 11644473600
                    import time
                    if expires_unix < time.time():
                        continue  # Cookie истекла
                
                cookies_dict[name] = value
            
            conn.close()
            os.remove(temp_cookies)
            
            print(f"[OK] Загружено {len(cookies_dict)} cookies из профиля Chrome")
            return cookies_dict
            
        except Exception as e:
            print(f"[ERROR] Ошибка загрузки cookies: {e}")
            return {}
    
    def create_session(self, cookies: Optional[Dict[str, str]] = None) -> requests.Session:
        """
        Создает сессию requests с cookies
        
        Args:
            cookies: Словарь с cookies. Если не указан, пытается загрузить из Chrome
        
        Returns:
            Объект requests.Session
        """
        if cookies is None:
            cookies = self.load_cookies_from_chrome()
        
        self.cookies = cookies
        self.session.cookies.update(cookies)
        
        # Устанавливаем стандартные headers для WB
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })
        
        return self.session
    
    def save_session(self, filepath: str):
        """Сохраняет сессию в файл"""
        session_data = {
            'cookies': dict(self.session.cookies),
            'headers': dict(self.session.headers)
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] Сессия сохранена: {filepath}")
    
    def load_session(self, filepath: str) -> requests.Session:
        """Загружает сессию из файла"""
        if not os.path.exists(filepath):
            print(f"[WARNING] Файл сессии не найден: {filepath}")
            return self.create_session()
        
        with open(filepath, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        
        self.session.cookies.update(session_data.get('cookies', {}))
        self.session.headers.update(session_data.get('headers', {}))
        
        print(f"[OK] Сессия загружена: {filepath}")
        return self.session

