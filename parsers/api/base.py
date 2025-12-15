# -*- coding: utf-8 -*-
"""
Базовый класс для API парсеров
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class BaseAPIParser(ABC):
    """Базовый класс для всех API парсеров"""
    
    def __init__(self):
        self.session = None
        self.errors = []
    
    @abstractmethod
    def get_prices(self, articles: List[str]) -> Dict[str, Dict]:
        """
        Получает цены для списка товаров
        
        Args:
            articles: Список артикулов
        
        Returns:
            Словарь {артикул: {price, priceAfterSPP, ...}}
        """
        pass
    
    def handle_error(self, error: Exception, article: Optional[str] = None):
        """
        Обрабатывает ошибку
        
        Args:
            error: Объект исключения
            article: Артикул товара (если применимо)
        """
        error_msg = f"[ERROR] {type(error).__name__}: {error}"
        if article:
            error_msg += f" (артикул: {article})"
        
        self.errors.append(error_msg)
        print(error_msg)
    
    def get_errors(self) -> List[str]:
        """Возвращает список ошибок"""
        return self.errors
    
    def clear_errors(self):
        """Очищает список ошибок"""
        self.errors = []

