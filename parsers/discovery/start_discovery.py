# -*- coding: utf-8 -*-
"""
Запуск discovery через mitmproxy
Простой скрипт для быстрого старта перехвата трафика
"""

import sys
import os
import asyncio

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from parsers.discovery.mitmproxy_capture import start_capture


if __name__ == "__main__":
    print("\n" + "="*70)
    print("DISCOVERY: Поиск внутренних API эндпоинтов")
    print("="*70)
    print("\nЭтот скрипт запустит mitmproxy для перехвата трафика.")
    print("Следуйте инструкциям на экране.\n")
    
    try:
        start_capture(port=8080)
    except KeyboardInterrupt:
        print("\n\nПерехват остановлен пользователем.")
    except Exception as e:
        print(f"\n[ERROR] Ошибка: {e}")
        import traceback
        traceback.print_exc()

