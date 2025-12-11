# -*- coding: utf-8 -*-
"""
СОЗДАНИЕ EXCEL ФАЙЛА СО ССЫЛКАМИ НА ТОВАРЫ
Читает артикулы из Excel и создаёт новый файл со ссылками
"""

import os
from openpyxl import load_workbook, Workbook

# Конфигурация
# Пути относительно корня проекта
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

EXCEL_FILE = os.path.join(DATA_DIR, "Парсер цен.xlsx")
SHEET_INPUT = "Данные для парсера ВБ"
OUTPUT_EXCEL_FILE = os.path.join(DATA_DIR, "links_to_products.xlsx")
SHEET_LINKS = "Ссылки на товары"

def main():
    print("\n" + "="*80)
    print("СОЗДАНИЕ EXCEL ФАЙЛА СО ССЫЛКАМИ")
    print("="*80)
    
    # Загружаем исходный Excel
    try:
        wb = load_workbook(EXCEL_FILE)
    except Exception as e:
        print(f"\n[!] ОШИБКА открытия Excel: {e}")
        print(f"    Убедись что файл '{EXCEL_FILE}' закрыт!")
        return
    
    ws_in = wb[SHEET_INPUT]
    
    # Загружаем артикулы
    articles = []
    for row in ws_in.iter_rows(min_row=2, max_col=1, values_only=True):
        if row[0]:
            articles.append(str(row[0]).strip())
    
    print(f"\n[1/2] Найдено артикулов: {len(articles)}")
    
    if len(articles) == 0:
        print("[!] Нет артикулов для обработки!")
        wb.close()
        return
    
    # Создаём новый Excel файл со ссылками
    print(f"\n[2/2] Создание файла со ссылками...")
    
    wb_out = Workbook()
    ws_out = wb_out.active
    ws_out.title = SHEET_LINKS
    
    # Заголовки
    ws_out.append(["ссылка на товар", "артикул"])
    
    # Генерируем ссылки
    for article in articles:
        product_url = f"https://www.wildberries.ru/catalog/{article}/detail.aspx"
        ws_out.append([product_url, article])
    
    # Автофильтр
    ws_out.auto_filter.ref = ws_out.dimensions
    
    # Сохраняем файл
    wb_out.save(OUTPUT_EXCEL_FILE)
    wb_out.close()
    wb.close()
    
    print(f"\n✓ Создано ссылок: {len(articles)}")
    print(f"✓ Файл сохранён: {OUTPUT_EXCEL_FILE}")
    print(f"✓ Лист: {SHEET_LINKS}")
    
    print(f"\n{'='*80}")
    print("ЗАВЕРШЕНО")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()


