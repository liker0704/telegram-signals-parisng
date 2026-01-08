# Анализ промптов для image editing

## Обзор

Система использует двухэтапную обработку изображений:
1. **Stage 1 (OCR)**: Vision провайдеры (Gemini/OpenAI/Anthropic) извлекают и переводят текст
2. **Stage 2 (Image Editing)**: Image editors (OpenAI/Gemini) генерируют новое изображение с переведённым текстом

В системе используются два типа промптов:
- **OCR Extraction Prompt** (`src/vision/prompts/ocr_extraction.py:127-186`) - для извлечения текста
- **Image Editing Prompts** - для генерации отредактированных изображений

---

## 1. OCR Extraction Prompt

### Местоположение
`src/vision/prompts/ocr_extraction.py:127-186`

### Использование
Промпт используется всеми vision провайдерами:
- `src/vision/providers/gemini.py:289` - передаётся в `extract_text()`
- `src/vision/providers/openai.py:193` - передаётся в `extract_text()`
- `src/vision/providers/anthropic.py` - аналогично

### Структура промпта

```
Extract ALL visible text from this trading chart/screenshot image.

IMPORTANT INSTRUCTIONS:
1. Find EVERY piece of text in the image (labels, numbers, symbols, annotations)
2. Text may be in Russian, English, or Cyrillic characters
3. Translate ALL Russian/Cyrillic text to English
4. Preserve exact formatting of: numbers, currency symbols ($, €, ₽), percentages (%), ticker symbols (BTC/USDT, ETH/USD)
5. For each text element, output BOTH original and English translation

OUTPUT FORMAT:
For each text element found, use this exact format:
ORIGINAL: [original text exactly as shown] -> ENGLISH: [English translation]

TRANSLATION RULES:
- If text is already in English → ENGLISH should be same as ORIGINAL
- If text contains numbers/symbols only → ENGLISH should be same as ORIGINAL
- If text is Russian/Cyrillic → translate to English
- Use trading-specific terminology:
  * ЛОНГ / ЛОН → LONG
  * ШОРТ → SHORT
  * Вход → Entry
  * Тейк / Тейк-профит → TP / Take Profit
  * Стоп / Стоп-лосс → SL / Stop Loss
  * БАЙБИТ → BYBIT
  * БИНАНС → BINANCE
  * Риск → Risk
  * Плечо → Leverage
  * Цена → Price
  * Цель → Target
  * Поддержка → Support
  * Сопротивление → Resistance

EXAMPLES:
✅ CORRECT:
ORIGINAL: ЛОНГ → ENGLISH: LONG
ORIGINAL: BTC/USDT → ENGLISH: BTC/USDT
ORIGINAL: 45,230.5 → ENGLISH: 45,230.5
ORIGINAL: Вход: 1.2345 → ENGLISH: Entry: 1.2345
ORIGINAL: Тейк 1 → ENGLISH: TP 1
ORIGINAL: Стоп-лосс → ENGLISH: Stop Loss
ORIGINAL: 5x → ENGLISH: 5x
ORIGINAL: БАЙБИТ → ENGLISH: BYBIT

❌ INCORRECT:
ORIGINAL: ЛОНГ → ENGLISH: Long (should be uppercase LONG)
ORIGINAL: Вход → ENGLISH: Entrance (should be Entry)
ORIGINAL: Тейк → ENGLISH: Take (should be TP)

SPECIAL CASES:
- Mixed text: "ЛОНГ BTC/USDT" → ENGLISH: "LONG BTC/USDT"
- Dates: "12.12.2025" → preserve as is
- Percentages: "3.5%" → preserve as is
- Decimal numbers: "1,234.56" or "1.234,56" → preserve format
- Chart labels: translate but keep technical meaning

If NO text is visible or readable in the image, return exactly:
NO_TEXT_FOUND

Otherwise, list ALL text elements in the format above, one per line.
```

### Парсинг ответа

**Gemini** (`src/vision/providers/gemini.py:145-237`):
- Ожидаемый формат: `ORIGINAL: <text> -> ENGLISH: <translation>`
- Нормализация стрелок: `→`, `➔`, `⟶` → `->` (строка 182)
- Разделение по первой стрелке: `split('->', 1)` (строка 191)
- Извлечение: `replace('ORIGINAL:', '').strip()` (строка 195-196)
- Пропуск пустых строк и строк без стрелки (строки 178-186)

**OpenAI** (`src/vision/providers/openai.py:98-162`):
- Идентичная логика парсинга
- Нормализация стрелок: `→`, `➔`, `⟶` → `->` (строка 129)
- Разделение: `split("->")` (строка 131)
- Игнорирование комментариев: пропуск строк с `#` или `//` (строка 121)

### Выявленные характеристики OCR промпта

**Сильные стороны:**
1. Чёткая структура вывода с примерами
2. Детальный словарь торговых терминов (124 термина в `TRADING_TERMS`)
3. Примеры правильного и неправильного использования
4. Специальная обработка особых случаев (даты, проценты, числа)
5. Явная инструкция для случая отсутствия текста (`NO_TEXT_FOUND`)

**Потенциальные проблемы:**
1. **Избыточность**: Промпт очень длинный (186 строк), содержит дублирующиеся инструкции
2. **Отсутствие приоритизации**: Не указано, какой текст важнее (например, торговые сигналы vs декоративный текст)
3. **Нет инструкций по позиционированию**: Не запрашивается информация о расположении текста на изображении
4. **Нет обработки шума**: Не указано, как обрабатывать нечитаемый или частично видимый текст
5. **Жёсткий формат вывода**: Требование стрелки `->` может вызвать ошибки парсинга при отклонениях LLM

---

## 2. OpenAI Image Editor Prompt

### Местоположение
`src/image_editing/openai_editor.py:227-253`

### Метод построения промпта
```python
def _build_prompt(self, translations: Dict[str, str]) -> str:
    if not translations:
        return (
            "Translate all Russian text in this image to English. "
            "Preserve the original formatting, colors, and layout exactly."
        )

    # Build a prompt with specific translations
    replacements = ", ".join(
        f"'{orig}' to '{trans}'"
        for orig, trans in translations.items()
    )

    return (
        f"Replace the following text in the image: {replacements}. "
        "Preserve the original formatting, colors, fonts, and layout exactly. "
        "Keep all other elements unchanged."
    )
```

### Пример сгенерированного промпта

**Случай 1: Без translations** (пустой словарь):
```
Translate all Russian text in this image to English. Preserve the original formatting, colors, and layout exactly.
```

**Случай 2: С конкретными translations**:
```
Replace the following text in the image: 'ЛОНГ' to 'LONG', 'Вход' to 'Entry', 'Тейк 1' to 'TP 1', 'Стоп' to 'SL'. Preserve the original formatting, colors, fonts, and layout exactly. Keep all other elements unchanged.
```

### API вызов
- **Endpoint**: `client.images.edit()` (строка 129)
- **Model**: `config.OPENAI_IMAGE_MODEL` (по умолчанию `"gpt-image-1"`)
- **Параметры**:
  - `image`: исходное изображение
  - `mask`: белая маска (полностью непрозрачная) - редактируется всё изображение (строки 255-287)
  - `prompt`: сгенерированный промпт
  - `n`: 1 (одно изображение)
  - `size`: "1024x1024" (фиксированный размер)

### Выявленные проблемы

**Критические проблемы:**

1. **Неоптимальная маска** (`src/image_editing/openai_editor.py:255-287`):
   ```python
   # Create a white mask (fully opaque)
   # OpenAI uses transparent areas as the edit region
   mask = Image.new("RGBA", img_rgba.size, (255, 255, 255, 255))
   ```
   - Создаётся полностью белая маска
   - Комментарий противоречив: "OpenAI uses transparent areas as the edit region"
   - Фактически редактируется всё изображение, а не только текстовые области
   - Это может приводить к изменению фона, графиков, линий

2. **Формат списка замен через запятую** (строка 244-247):
   ```python
   replacements = ", ".join(
       f"'{orig}' to '{trans}'"
       for orig, trans in translations.items()
   )
   ```
   - При большом количестве переводов (>10) промпт становится длинным и нечитаемым
   - Пример: `'ЛОНГ' to 'LONG', 'ШОРТ' to 'SHORT', 'Вход' to 'Entry', ...` (может быть 20-30 пар)
   - OpenAI может пропустить некоторые замены в конце списка

3. **Фиксированный размер "1024x1024"** (строка 135):
   - Все изображения ресайзятся к 1024x1024
   - Искажение пропорций для не-квадратных изображений
   - Потеря качества при апскейле маленьких изображений
   - Потеря деталей при даунскейле больших изображений

4. **Отсутствие инструкций по шрифту**:
   - Не указывается семейство шрифтов
   - Не указывается размер шрифта
   - OpenAI может использовать дефолтные шрифты, которые не соответствуют оригиналу

5. **Нечёткая инструкция "exactly"**:
   - "Preserve the original formatting, colors, fonts, and layout exactly"
   - Слово "exactly" субъективно и не гарантирует точного совпадения
   - Нет метрик качества или критериев успеха

6. **Отсутствие контекста изображения**:
   - Не указывается, что это торговый график
   - Не указываются важные элементы (цена, индикаторы, сигналы)
   - OpenAI не знает, что критично сохранить

---

## 3. Gemini Image Editor Prompt

### Местоположение
`src/image_editing/gemini_editor.py:211-239`

### Метод построения промпта
```python
def _build_prompt(self, translations: Dict[str, str]) -> str:
    if not translations:
        return (
            "Translate all Russian text in this image to English. "
            "Preserve the original formatting, colors, and layout. "
            "Return the edited image with English text."
        )

    # Build a prompt with specific translations
    replacements = "\n".join(
        f"- '{orig}' → '{trans}'"
        for orig, trans in translations.items()
    )

    return (
        f"Edit this image by replacing the following text:\n\n{replacements}\n\n"
        "Preserve the original formatting, colors, fonts, and layout exactly. "
        "Keep all other elements of the image unchanged. "
        "Return the edited image with the text replaced."
    )
```

### Пример сгенерированного промпта

**Случай 1: Без translations**:
```
Translate all Russian text in this image to English. Preserve the original formatting, colors, and layout. Return the edited image with English text.
```

**Случай 2: С конкретными translations**:
```
Edit this image by replacing the following text:

- 'ЛОНГ' → 'LONG'
- 'Вход' → 'Entry'
- 'Тейк 1' → 'TP 1'
- 'Стоп' → 'SL'

Preserve the original formatting, colors, fonts, and layout exactly. Keep all other elements of the image unchanged. Return the edited image with the text replaced.
```

### API вызов
- **Endpoint**: `client.models.generate_content()` (строка 123)
- **Model**: `config.GEMINI_IMAGE_MODEL` (по умолчанию `"gemini-2.5-flash-image"`)
- **Content**: `[prompt, {"mime_type": "image/jpeg", "data": image_data}]`
- **Нет параметра mask**: Gemini обрабатывает изображение целиком

### Сравнение с OpenAI

**Преимущества Gemini промпта:**
1. **Список с маркерами**: Использует `\n` и `-` для разделения (строка 229-232)
   - Более читаемый формат для LLM
   - Проще различить отдельные замены
   - Лучше для большого количества переводов

2. **Unicode стрелка `→`**: Визуально понятнее, чем `to`

3. **Явная инструкция возврата**: "Return the edited image with the text replaced"

**Общие проблемы с OpenAI:**
1. Отсутствие инструкций по шрифту
2. Нечёткая инструкция "exactly"
3. Отсутствие контекста изображения
4. Нет обработки случая, когда текст не найден

**Уникальные проблемы Gemini:**
1. Нет контроля размера изображения (API сам выбирает размер)
2. Нет возможности использовать маску для выборочного редактирования

---

## 4. Поток данных

### Полный пайплайн (src/ocr/image_editor.py:156-249)

```
1. Загрузка изображения (строка 183-194)
   └─> Апскейл до min 1024px если нужно

2. Stage 1: OCR Extraction (строка 196-212)
   ├─> extract_text_from_image(image)
   │   └─> Vision chain с OCR_EXTRACTION_PROMPT
   │       └─> Вывод: List[{russian, english}]
   └─> Конвертация в Dict[str, str]: {russian: english}

3. Stage 2: Image Editing (строка 214-246)
   ├─> ImageEditorFactory.get_editor_with_fallback()
   │   └─> OpenAI или Gemini editor
   ├─> editor.edit_image(image_path, translations_dict, output_path)
   │   ├─> _build_prompt(translations_dict)
   │   ├─> API call (OpenAI images.edit() или Gemini generate_content())
   │   └─> Возврат EditResult
   └─> Сохранение результата
```

### Критический момент
Между Stage 1 и Stage 2 есть потеря информации:
- **Stage 1** возвращает: `{original: translated, confidence: float}`
- **Stage 2** получает: `{russian: english}` (без confidence)
- **Проблема**: Низкоуверенные переводы обрабатываются так же, как высокоуверенные

---

## 5. Тестовые данные

Найдены тестовые изображения:
- `tests/data/mock_images/signal_russian_only.png`
- `tests/data/mock_images/signal_ocr_1.png`
- `tests/data/mock_images/signal_ocr_2.png`
- `tests/data/mock_images/signal_ocr_3.png`

Однако в тестах (`tests/test_openai_integration.py`) нет интеграционных тестов для image editing:
- Есть синтаксические проверки (строки 56-74)
- Есть проверки импортов (строки 99-108)
- **НЕТ** тестов с реальными вызовами API
- **НЕТ** валидации качества промптов
- **НЕТ** сравнения результатов OpenAI vs Gemini

---

## 6. Конфигурация

### Используемые модели
- **OpenAI Vision**: `config.OPENAI_VISION_MODEL` (по умолчанию `"gpt-4o"`)
- **OpenAI Image Edit**: `config.OPENAI_IMAGE_MODEL` (по умолчанию `"gpt-image-1"`)
- **Gemini Vision**: `config.GEMINI_MODEL` (по умолчанию `"gemini-2.5-flash"`)
- **Gemini Image Edit**: `config.GEMINI_IMAGE_MODEL` (по умолчанию `"gemini-2.5-flash-image"`)

### Fallback chain
- Vision: `config.VISION_FALLBACK` (строка в формате `"gemini,openai,anthropic"`)
- Image editor: Хардкод в `ImageEditorFactory` - OpenAI → Gemini

---

## 7. Выводы

### Качество промптов

**OCR Extraction Prompt: 7/10**
- Сильная сторона: детальная спецификация формата вывода
- Слабая сторона: избыточность, отсутствие приоритизации

**OpenAI Image Editor Prompt: 4/10**
- Критические проблемы: маска, формат списка, фиксированный размер
- Отсутствие важного контекста

**Gemini Image Editor Prompt: 5/10**
- Лучше структурирован, чем OpenAI
- Те же концептуальные проблемы

### Приоритетные проблемы для исправления

1. **OpenAI маска**: Нужна интеллектуальная маска только для текстовых областей
2. **Размер изображения**: Сохранять оригинальные пропорции
3. **Формат замен**: Использовать структурированный список вместо comma-separated
4. **Контекст**: Добавить информацию о типе изображения (trading chart)
5. **Шрифты**: Указать требования к шрифтам (семейство, размер, вес)
6. **Фильтрация по confidence**: Использовать только высокоуверенные переводы

---

## Метаданные анализа

```yaml
---
status: SUCCESS
files_analyzed: 8
symbols_traced: 12
data_flows_documented: 2
patterns_identified:
  - Two-stage pipeline (OCR + Image Edit)
  - Factory pattern for editor selection
  - Fallback chain for providers
  - Lazy initialization with thread safety
confidence: high
---
```

### Файлы проанализированы:
1. `src/image_editing/openai_editor.py` - OpenAI editor implementation
2. `src/image_editing/gemini_editor.py` - Gemini editor implementation
3. `src/image_editing/base.py` - Base interfaces
4. `src/vision/prompts/ocr_extraction.py` - OCR prompt
5. `src/vision/providers/gemini.py` - Gemini vision provider
6. `src/vision/providers/openai.py` - OpenAI vision provider
7. `src/ocr/image_editor.py` - Main pipeline orchestration
8. `tests/test_openai_integration.py` - Tests

### Ключевые функции прослежены:
- `OpenAIImageEditor._build_prompt()` (строки 227-253)
- `GeminiImageEditor._build_prompt()` (строки 211-239)
- `OpenAIImageEditor.edit_image()` (строки 70-199)
- `GeminiImageEditor.edit_image()` (строки 69-183)
- `OpenAIImageEditor._create_mask()` (строки 255-287)
- `extract_text_from_image()` (строки 80-120)
- `edit_image_text_sync()` (строки 156-249)
- `GeminiVisionProvider._parse_response()` (строки 145-237)
- `OpenAIVisionProvider._parse_response()` (строки 98-162)

### Потоки данных:
1. **OCR Flow**: Image → Vision Provider → OCR_EXTRACTION_PROMPT → Parse Response → List[TextExtraction]
2. **Edit Flow**: Image + Translations Dict → Image Editor → _build_prompt() → API Call → Edited Image
