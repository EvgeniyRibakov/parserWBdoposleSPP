# Правила парсинга цен Wildberries

## Логика извлечения цены с карточки товара

### Проблема
На некоторых страницах товаров WB отображается две цены:
- **Цена с кошельком WB** (красная кнопка) - со скидкой при оплате кошельком
- **Финальная цена** (черный текст) - итоговая цена с учетом всех скидок

### Решение

#### Шаг 1: Клик по кнопке кошелька
Сначала нужно найти и кликнуть на кнопку с ценой кошелька:
- **HTML элемент**: `<button class="mo-button ... priceBlockWalletPrice--RJGuT">`
- **CSS селектор**: `button[class*='priceBlockWalletPrice']`

**Пример из `code_pages\elements\tap_find_black_price.html`:**
```html
<button class="mo-button ... priceBlockWalletPrice--RJGuT" type="button">
  <h2 class="mo-typography ...">349&nbsp;₽</h2>
</button>
```

#### Шаг 2: Извлечение финальной цены
После клика появляется элемент с итоговой ценой:
- **HTML элемент**: `<h2 class="mo-typography ... mo-typography_color_primary">`
- **CSS селектор**: `h2.mo-typography_color_primary` или `h2[class*='mo-typography'][class*='color_primary']`
- **Значение**: Число с неразрывными пробелами (например: `364&nbsp;₽`)

**Пример из `code_pages\elements\copy_black_price.html`:**
```html
<h2 class="mo-typography mo-typography_variant_title2 ... mo-typography_color_primary">364&nbsp;₽</h2>
```

### Реализация в коде

```python
# 1. Пытаемся кликнуть на кнопку кошелька
try:
    wallet_button = WebDriverWait(driver, 3).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[class*='priceBlockWalletPrice']"))
    )
    wallet_button.click()
    time.sleep(1)  # Ждем появления финальной цены
except:
    pass  # Кнопки нет - используем обычную цену

# 2. Извлекаем финальную цену (приоритет 1)
price_selectors = [
    (By.CSS_SELECTOR, "h2.mo-typography_color_primary"),  # После клика на кошелек
    (By.CSS_SELECTOR, "ins[class*='priceBlockFinalPrice']"),  # Обычная цена (fallback)
]

for by, selector in price_selectors:
    try:
        price_elem = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((by, selector))
        )
        price_text = price_elem.text.strip()
        # Убираем все нецифровые символы (включая &nbsp;)
        price = int(re.sub(r'[^\d]', '', price_text))
        break
    except:
        continue
```

### Примечания
- Не на всех товарах есть кнопка кошелька - в таком случае используется обычная цена
- Финальная цена всегда **ниже или равна** цене с кошельком
- При парсинге нужно убирать все нецифровые символы, включая:
  - Неразрывные пробелы (`&nbsp;`)
  - Символ рубля (`₽`)
  - Обычные пробелы

### Тестовые данные
- **Пример страницы**: `code_pages\pages\product_page_example.html`
- **Цена с кошельком**: 349 ₽
- **Финальная цена**: 364 ₽

