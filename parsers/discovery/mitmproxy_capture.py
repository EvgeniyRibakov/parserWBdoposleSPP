# -*- coding: utf-8 -*-
"""
DISCOVERY: Перехват трафика через mitmproxy для поиска внутренних API эндпоинтов
Используется для поиска запросов, которые возвращают цены после СПП (WB) и цены с картой (Ozon)
"""

import json
import os
import asyncio
from datetime import datetime
from mitmproxy import http
from mitmproxy.tools.dump import DumpMaster
from mitmproxy.options import Options

# Директория для сохранения перехваченных запросов
CAPTURE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "captured_requests")
os.makedirs(CAPTURE_DIR, exist_ok=True)

# Фильтры для интересующих доменов
WB_DOMAINS = ["wildberries.ru", "wb.ru", "wbbasket.ru"]
OZON_DOMAINS = ["ozon.ru", "ozon.ru"]

# Счетчики
captured_requests = []
wb_requests = []
ozon_requests = []


class APIRequestCapture:
    """Класс для перехвата и сохранения API запросов"""
    
    def __init__(self):
        self.captured_count = 0
        self.wb_count = 0
        self.ozon_count = 0
    
    def request(self, flow: http.HTTPFlow) -> None:
        """Обработка исходящих запросов"""
        url = flow.request.pretty_url
        host = flow.request.host
        
        # Фильтруем только интересующие домены
        is_wb = any(domain in host for domain in WB_DOMAINS)
        is_ozon = any(domain in host for domain in OZON_DOMAINS)
        
        if not (is_wb or is_ozon):
            return
        
        # Сохраняем информацию о запросе
        request_data = {
            "timestamp": datetime.now().isoformat(),
            "method": flow.request.method,
            "url": url,
            "host": host,
            "path": flow.request.path,
            "headers": dict(flow.request.headers),
            "query": dict(flow.request.query),
            "content": flow.request.content.decode('utf-8', errors='ignore') if flow.request.content else None,
            "platform": "WB" if is_wb else "OZON"
        }
        
        captured_requests.append(request_data)
        
        if is_wb:
            self.wb_count += 1
            wb_requests.append(request_data)
        elif is_ozon:
            self.ozon_count += 1
            ozon_requests.append(request_data)
        
        self.captured_count += 1
        
        # Выводим информацию в консоль
        print(f"\n[CAPTURE] {request_data['platform']} - {flow.request.method} {flow.request.path}")
        if flow.request.query:
            print(f"  Query: {dict(flow.request.query)}")
    
    def response(self, flow: http.HTTPFlow) -> None:
        """Обработка ответов"""
        host = flow.request.host
        
        is_wb = any(domain in host for domain in WB_DOMAINS)
        is_ozon = any(domain in host for domain in OZON_DOMAINS)
        
        if not (is_wb or is_ozon):
            return
        
        # Ищем запрос в списке перехваченных
        request_data = None
        for req in captured_requests:
            if req["url"] == flow.request.pretty_url and req["timestamp"]:
                request_data = req
                break
        
        if not request_data:
            return
        
        # Добавляем информацию об ответе
        try:
            response_data = {
                "status_code": flow.response.status_code,
                "headers": dict(flow.response.headers),
                "content": flow.response.content.decode('utf-8', errors='ignore') if flow.response.content else None,
            }
            
            # Пытаемся распарсить JSON
            if response_data["content"]:
                try:
                    response_data["json"] = json.loads(response_data["content"])
                except:
                    pass
            
            request_data["response"] = response_data
            
            # Сохраняем в файл, если это интересный запрос (содержит цены)
            if response_data.get("json"):
                content_str = json.dumps(response_data["json"], ensure_ascii=False, indent=2)
                # Ищем ключевые слова, связанные с ценами
                price_keywords = ["price", "цена", "cost", "discount", "spp", "card", "wallet", "loyalty"]
                if any(keyword.lower() in content_str.lower() for keyword in price_keywords):
                    self.save_interesting_request(request_data)
        
        except Exception as e:
            print(f"[ERROR] Ошибка обработки ответа: {e}")
    
    def save_interesting_request(self, request_data: dict):
        """Сохраняет интересный запрос в файл"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        platform = request_data["platform"]
        filename = f"{platform}_{timestamp}_{request_data['method']}.json"
        filepath = os.path.join(CAPTURE_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(request_data, f, ensure_ascii=False, indent=2)
        
        print(f"[SAVED] Сохранен интересный запрос: {filename}")
    
    def done(self):
        """Вызывается при завершении работы"""
        print(f"\n{'='*60}")
        print(f"ИТОГИ ПЕРЕХВАТА")
        print(f"{'='*60}")
        print(f"Всего перехвачено: {self.captured_count}")
        print(f"WB запросов: {self.wb_count}")
        print(f"Ozon запросов: {self.ozon_count}")
        print(f"\nСохраненные запросы находятся в: {CAPTURE_DIR}")
        
        # Сохраняем сводку
        summary_file = os.path.join(CAPTURE_DIR, f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        summary = {
            "total_captured": self.captured_count,
            "wb_requests": self.wb_count,
            "ozon_requests": self.ozon_count,
            "all_requests": captured_requests
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"Сводка сохранена: {summary_file}")


def start_capture(port=8080):
    """
    Запускает mitmproxy для перехвата трафика
    
    Использование:
    1. Запустить этот скрипт
    2. Настроить браузер на использование прокси localhost:8080
    3. Открыть ЛК покупателя WB или Ozon
    4. Открыть карточки товаров
    5. Нажать Ctrl+C для остановки
    """
    print(f"\n{'='*60}")
    print("MITMPROXY CAPTURE - ПЕРЕХВАТ ТРАФИКА")
    print(f"{'='*60}")
    print(f"\nПрокси запущен на порту: {port}")
    print(f"\nИНСТРУКЦИЯ:")
    print(f"1. Настройте браузер на использование прокси: localhost:{port}")
    print(f"2. Откройте ЛК покупателя WB (wildberries.ru)")
    print(f"3. Откройте карточки товаров с СПП")
    print(f"4. Для Ozon: откройте карточки товаров с картой лояльности")
    print(f"5. Нажмите Ctrl+C для остановки перехвата")
    print(f"\nПерехваченные запросы будут сохранены в: {CAPTURE_DIR}")
    print(f"{'='*60}\n")
    
    addon = APIRequestCapture()
    # Указываем явно listen_host для прослушивания на всех интерфейсах
    opts = Options(listen_host='0.0.0.0', listen_port=port)
    
    # Правильный способ запуска mitmproxy с event loop
    import sys
    
    if sys.platform == 'win32':
        # На Windows используем SelectorEventLoop
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Правильный способ: используем asyncio.run() с async функцией
    async def run_proxy():
        master = DumpMaster(opts)
        master.addons.add(addon)
        await master.run()
    
    # Запускаем через asyncio.run()
    try:
        asyncio.run(run_proxy())
    except KeyboardInterrupt:
        print("\n\nОстановка перехвата...")
        addon.done()


if __name__ == "__main__":
    start_capture()

