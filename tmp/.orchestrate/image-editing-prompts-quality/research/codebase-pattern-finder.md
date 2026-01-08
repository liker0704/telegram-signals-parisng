# Prompt Patterns Analysis - Image Editing в Кодовой Базе

## Обнаруженные паттерны промптов

### Pattern 1: Детальный структурированный промпт (OCR Vision)

**Найдено в**: `/home/liker/projects/telegram-signals-parisng/src/vision/prompts/ocr_extraction.py:127-186`

**Используется для**: Извлечение и перевод текста с торговых графиков

**Структура промпта**:

```python
OCR_EXTRACTION_PROMPT = """Extract ALL visible text from this trading chart/screenshot image.

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
"""
```

**Ключевые аспекты**:
- **Структурированный формат**: Четкие разделы (INSTRUCTIONS, OUTPUT FORMAT, TRANSLATION RULES, EXAMPLES, SPECIAL CASES)
- **Детальная документация**: Пронумерованные инструкции и bullet points
- **Примеры правильного/неправильного использования**: ✅ CORRECT / ❌ INCORRECT секция
- **Специализированная терминология**: Словарь `TRADING_TERMS` (124 элемента) в том же файле (строки 4-124)
- **Edge cases**: Секция SPECIAL CASES для обработки нестандартных ситуаций
- **Формат вывода**: Строго определенный формат `ORIGINAL: ... -> ENGLISH: ...`
- **Fallback сценарий**: Явная инструкция для случая "NO_TEXT_FOUND"

**Используется в**:
- `/home/liker/projects/telegram-signals-parisng/src/vision/providers/gemini.py:289` (по умолчанию)
- `/home/liker/projects/telegram-signals-parisng/src/vision/providers/openai.py:193` (по умолчанию)
- `/home/liker/projects/telegram-signals-parisng/src/vision/providers/anthropic.py:193` (по умолчанию)

---

### Pattern 2: Простой промпт с контекстом (Translation)

**Найдено в**: `/home/liker/projects/telegram-signals-parisng/src/translators/openai.py:42-49`

**Используется для**: Перевод текстовых торговых сигналов

```python
prompt = f'''Translate the following trading signal text from Russian to English.
Keep all trading terms, numbers, ticker symbols, and formatting intact.
Only translate the Russian text to English.

Text to translate:
{text}

Return ONLY the translated text, nothing else.'''
```

**Ключевые аспекты**:
- **Краткий и прямой**: Всего 3 инструкции
- **Встроенные данные**: Использует f-string для вставки текста
- **Контекстные ограничения**: "Keep all trading terms, numbers, ticker symbols, and formatting intact"
- **Явный формат вывода**: "Return ONLY the translated text, nothing else"
- **Без примеров**: Нет секции с примерами

**Используется в**:
- `/home/liker/projects/telegram-signals-parisng/src/translators/openai.py:51-58` (chat.completions.create)
- Идентичный промпт в `/home/liker/projects/telegram-signals-parisng/src/translators/gemini.py:36-43`

**Параметры API**:
- `temperature=0.3` (низкая креативность)
- `max_tokens=2000`

---

### Pattern 3: Промпт для image editing - OpenAI (comma-separated)

**Найдено в**: `/home/liker/projects/telegram-signals-parisng/src/image_editing/openai_editor.py:227-253`

**Используется для**: Редактирование текста на изображениях через OpenAI API

```python
def _build_prompt(self, translations: Dict[str, str]) -> str:
    """Build a prompt for OpenAI based on the translations."""
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

**Ключевые аспекты**:
- **Динамическая генерация**: Промпт строится из словаря переводов
- **Comma-separated формат**: `'ЛОНГ' to 'LONG', 'Вход' to 'Entry'`
- **Fallback вариант**: Если нет переводов, используется общий промпт
- **Акцент на сохранении**: "Preserve the original formatting, colors, fonts, and layout exactly"
- **Краткий**: Нет примеров или детальных инструкций
- **Две инструкции**: Replace + Preserve

**Используется в**:
- `/home/liker/projects/telegram-signals-parisng/src/image_editing/openai_editor.py:117` перед вызовом API
- Вызывается с `client.images.edit()` (строка 129)

---

### Pattern 4: Промпт для image editing - Gemini (bullet list)

**Найдено в**: `/home/liker/projects/telegram-signals-parisng/src/image_editing/gemini_editor.py:211-239`

**Используется для**: Редактирование текста на изображениях через Gemini API

```python
def _build_prompt(self, translations: Dict[str, str]) -> str:
    """Build a prompt for Gemini based on the translations."""
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

**Ключевые аспекты**:
- **Bullet list формат**: `- 'ЛОНГ' → 'LONG'\n- 'Вход' → 'Entry'`
- **Использует Unicode стрелку**: → вместо обычного "to"
- **Структурированный вывод**: Список на отдельных строках с пустыми строками до/после
- **Явное требование результата**: "Return the edited image with the text replaced"
- **Три инструкции**: Edit + Preserve + Return
- **Fallback вариант**: Общий промпт если нет переводов

**Используется в**:
- `/home/liker/projects/telegram-signals-parisng/src/image_editing/gemini_editor.py:114` перед вызовом API
- Вызывается с `client.models.generate_content()` (строка 123)

---

### Pattern 5: Простой OCR промпт (legacy Gemini OCR)

**Найдено в**: `/home/liker/projects/telegram-signals-parisng/src/ocr/gemini_ocr.py:61-73`

**Используется для**: Простое извлечение текста (старый метод)

```python
prompt = '''Extract ALL visible text from this trading chart/screenshot image.
If text is visible, translate any Russian text to English.
Preserve numbers, currency symbols ($, €), and ticker symbols (e.g., BTC/USDT, %) exactly.

If NO readable text is found on the image, return exactly: NO_TEXT_FOUND

Return in this format:
EXTRACTED: [original text from image]
TRANSLATED: [english translation if needed, or same as extracted if already English]

If no text found:
EXTRACTED: (none)
TRANSLATED: (none)'''
```

**Ключевые аспекты**:
- **Упрощенная версия**: Меньше деталей чем OCR_EXTRACTION_PROMPT
- **Формат EXTRACTED/TRANSLATED**: Отличается от детального промпта
- **Нет примеров**: Только базовые инструкции
- **Нет специальной терминологии**: Общие инструкции для валют/тикеров
- **Fallback**: NO_TEXT_FOUND или (none)

**Используется в**:
- `/home/liker/projects/telegram-signals-parisng/src/ocr/gemini_ocr.py:76` (устаревший метод)

---

## Паттерны использования промптов

### Паттерн A: Централизованное хранение промптов

**Расположение**: `/home/liker/projects/telegram-signals-parisng/src/vision/prompts/`

**Структура**:
```python
# src/vision/prompts/__init__.py
from src.vision.prompts.ocr_extraction import (
    OCR_EXTRACTION_PROMPT,
    TRADING_TERMS,
)

__all__ = [
    'OCR_EXTRACTION_PROMPT',
    'TRADING_TERMS',
]
```

**Использование**:
- Импортируется как `from src.vision.prompts import OCR_EXTRACTION_PROMPT`
- Используется в 3 vision providers (Gemini, OpenAI, Anthropic)
- Единый источник истины для OCR промптов

---

### Паттерн B: Inline промпты в методах

**Расположение**: `src/translators/*.py`, `src/image_editing/*.py`

**Характеристики**:
- Промпты определяются прямо в функциях/методах
- Часто используют f-strings для динамического контента
- Дублирование между `openai.py` и `gemini.py` (идентичные промпты)

**Примеры**:
- Translation промпт дублируется в `src/translators/openai.py:42` и `src/translators/gemini.py:36`
- Image editing промпты в методах `_build_prompt()` в обоих редакторах

---

### Паттерн C: Динамическое построение промптов

**Найдено в**: Image editing модулях

**Метод**:
```python
def _build_prompt(self, translations: Dict[str, str]) -> str:
    if not translations:
        return "General fallback prompt..."

    # Build dynamic part from data
    replacements = FORMAT.join(
        f"template {orig} {trans}"
        for orig, trans in translations.items()
    )

    return f"Prefix {replacements} Suffix"
```

**Вариации**:
- **OpenAI**: Comma-separated inline список
- **Gemini**: Bullet list с переносами строк

---

## Параметры API для промптов

### Vision API (OCR)

**Общие параметры** (все 3 провайдера):
```python
temperature = 0  # Детерминированный вывод
```

**Используется в**:
- `src/vision/providers/gemini.py:91`
- `src/vision/providers/openai.py:50`
- `src/vision/providers/anthropic.py:50`

### Translation API

**OpenAI**:
```python
temperature = 0.3
max_tokens = 2000  # Из config.OPENAI_TRANSLATE_MAX_TOKENS
```

**Gemini**:
- Используются дефолтные параметры модели
- Не указаны явно в коде

---

## Обработка ответов от LLM

### Паттерн парсинга: Структурированный текстовый формат

**Используется в**: Все vision providers

**Ожидаемый формат**:
```
ORIGINAL: <text> -> ENGLISH: <translation>
```

**Парсинг**:
```python
def _parse_response(self, raw_text: str) -> List[TextExtraction]:
    extractions = []

    # Check for NO_TEXT_FOUND
    if "NO_TEXT_FOUND" in raw_text:
        return extractions

    for line in raw_text.split('\n'):
        # Normalize Unicode arrows
        normalized_line = line.replace("→", "->").replace("➔", "->")

        if 'ORIGINAL:' in line and 'ENGLISH:' in line:
            parts = normalized_line.split('->', 1)
            original = parts[0].replace('ORIGINAL:', '').strip()
            english = parts[1].replace('ENGLISH:', '').strip()

            extractions.append(TextExtraction(
                original=original,
                translated=english,
                confidence=1.0
            ))

    return extractions
```

**Найдено в**:
- `src/vision/providers/gemini.py:145-237`
- `src/vision/providers/openai.py:98-162` (идентичная логика)
- `src/vision/providers/anthropic.py:98-162` (идентичная логика)

**Ключевые особенности**:
- Нормализация Unicode стрелок (→, ➔, ⟶) в ASCII (->)
- Обработка "NO_TEXT_FOUND" кейса
- Пропуск пустых строк и комментариев
- Split только по первой стрелке (`, 1`)
- Установка фиксированной confidence=1.0

---

## Сравнение промптов для image editing

### Различия между OpenAI и Gemini промптами

| Аспект | OpenAI | Gemini |
|--------|--------|--------|
| **Формат списка замен** | Comma-separated inline | Bullet list с переносами |
| **Разделитель** | `, ` | `\n` |
| **Стрелка** | `to` (текст) | `→` (Unicode) |
| **Пример** | `'A' to 'B', 'C' to 'D'` | `- 'A' → 'B'\n- 'C' → 'D'` |
| **Структура** | Inline, компактно | Вертикально, с пустыми строками |
| **Количество инструкций** | 2 (Replace + Preserve) | 3 (Edit + Preserve + Return) |
| **Явное требование результата** | Нет | Да ("Return the edited image") |

### Код генерации

**OpenAI** (`openai_editor.py:244-246`):
```python
replacements = ", ".join(
    f"'{orig}' to '{trans}'"
    for orig, trans in translations.items()
)
```

**Gemini** (`gemini_editor.py:229-232`):
```python
replacements = "\n".join(
    f"- '{orig}' → '{trans}'"
    for orig, trans in translations.items()
)
```

---

## Общие паттерны промпт-инжиниринга в кодовой базе

### 1. Структура "Инструкции → Правила → Примеры"

Используется в детальных промптах (OCR_EXTRACTION_PROMPT):
- **INSTRUCTIONS**: Что делать
- **RULES**: Как делать
- **EXAMPLES**: Примеры правильного/неправильного
- **SPECIAL CASES**: Edge cases

### 2. Явное определение формата вывода

Все промпты включают секцию "OUTPUT FORMAT" или "Return in this format":
- Точное описание ожидаемой структуры
- Примеры формата
- Fallback случаи (NO_TEXT_FOUND, (none))

### 3. Контекстные ограничения

Почти все промпты включают "Preserve..." инструкции:
- "Preserve exact formatting"
- "Preserve numbers, currency symbols"
- "Keep all trading terms intact"

### 4. Специализированная терминология

OCR промпт включает:
- Словарь 124 терминов (`TRADING_TERMS`)
- Inline примеры терминологии в секции TRANSLATION RULES
- Конкретные замены (ЛОНГ → LONG, а не Long)

### 5. Fallback сценарии

Все промпты обрабатывают пустые/недостающие данные:
- `if not translations:` → общий промпт
- `NO_TEXT_FOUND` → пустой результат
- `EXTRACTED: (none)` → явная индикация отсутствия

### 6. Детерминированность через temperature

Vision задачи используют `temperature=0` для консистентности:
- OCR должен быть детерминированным
- Translation использует `temperature=0.3` (небольшая вариативность приемлема)

---

## Качество и детализация промптов

### Высокая детализация (OCR_EXTRACTION_PROMPT)

**Характеристики**:
- 186 строк кода (включая словарь терминов)
- 59 строк чистого промпта
- 7 секций (INSTRUCTIONS, OUTPUT FORMAT, TRANSLATION RULES, EXAMPLES, SPECIAL CASES)
- 8 примеров CORRECT, 3 примера INCORRECT
- 5 special cases
- 18 специализированных терминов в inline инструкциях

**Результат**:
- Используется всеми 3 vision providers без модификаций
- Единый источник истины
- Высокая консистентность парсинга

### Низкая детализация (Image editing промпты)

**Характеристики**:
- 2-3 предложения
- Нет примеров
- Нет специальных случаев
- Динамическая генерация
- Общие инструкции

**Результат**:
- Вариативность результатов (отмечено в analyzer как проблема)
- Нет гарантии сохранения формата/стиля
- Белая маска в OpenAI редактирует всё изображение

---

## Паттерны тестирования промптов

### Тестов промптов не найдено

**Поиск показал**:
- `tests/**/*vision*.py` - нет файлов
- `tests/**/*ocr*.py` - нет файлов
- `tests/**/*image*.py` - нет файлов
- `test.*prompt|prompt.*test` - нет результатов

**Вывод**:
- Промпты не покрыты автоматическими тестами
- Нет unit-тестов для проверки качества промптов
- Нет integration тестов для проверки парсинга ответов

---

## Используемые LLM модели

### Конфигурация моделей

**Из** `/home/liker/projects/telegram-signals-parisng/src/config.py`:

```python
# Vision OCR
GEMINI_MODEL: str = "gemini-2.0-flash"  # default
OPENAI_VISION_MODEL: str = "gpt-4o"  # default
ANTHROPIC_VISION_MODEL: str = "claude-sonnet-4-20250514"  # default

# Translation
OPENAI_TRANSLATE_MODEL: str = "gpt-4o-mini"  # default

# Image Editing
GEMINI_IMAGE_MODEL: str = "gemini-2.5-flash-image"  # default
OPENAI_IMAGE_MODEL: str = "gpt-image-1"  # default
```

### Выбор провайдера

**Из config** (строки 99-114):
```python
VISION_PROVIDER: str = "gemini"  # default
VISION_FALLBACK_PROVIDERS: str = "openai,anthropic"  # default
IMAGE_EDITOR: str = "openai"  # default
IMAGE_EDITOR_FALLBACK: str = "gemini"  # default
```

---

## Выводы

### Найденные паттерны промптов

1. **Детальный структурированный промпт** (OCR) - высокое качество, много деталей
2. **Простой контекстный промпт** (Translation) - минималистичный, эффективный
3. **Динамический промпт с comma-separated** (OpenAI editing) - компактный формат
4. **Динамический промпт с bullet list** (Gemini editing) - структурированный формат
5. **Простой OCR промпт** (legacy) - базовая функциональность

### Качество промптов по категориям

**OCR/Vision**: ⭐⭐⭐⭐⭐
- Детальные инструкции
- Множество примеров
- Специализированная терминология
- Обработка edge cases

**Translation**: ⭐⭐⭐⭐
- Краткие и эффективные
- Контекстные ограничения
- Нет примеров (но работает)

**Image Editing**: ⭐⭐
- Минимальная детализация
- Нет примеров
- Нет специальных случаев
- Вариативность результатов

### Паттерны организации

1. **Централизованное хранение** для переиспользуемых промптов
2. **Inline определение** для специфичных промптов
3. **Динамическая генерация** для data-driven промптов
4. **Дублирование** между провайдерами (translation промпты идентичны)

---
status: SUCCESS
patterns_found: 5
code_examples: 9
categories:
  vision_ocr: 2
  translation: 1
  image_editing: 2
confidence: high
---
