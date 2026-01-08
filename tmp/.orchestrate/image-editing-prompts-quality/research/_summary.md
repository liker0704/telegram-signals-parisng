# Image Editing Prompts Quality: Research Synthesis

## Executive Summary

Система использует двухэтапный пайплайн (OCR extraction + Image editing) для перевода текста на торговых сигналах. **OCR промпт высокого качества (7/10)**, но **image editing промпты критически недоработаны (4-5/10)**: неправильная маска OpenAI, слишком краткие инструкции, отсутствие контекста изображения и явных инвариантов. Web-исследование подтверждает необходимость детальных промптов с явным перечислением сохраняемых элементов и правильной работы с alpha-каналом масок.

---

## Key Discoveries by Agent

### 1. Codebase Locator (32 файла найдено)

**Ключевые файлы промптов:**
- `/home/liker/projects/telegram-signals-parisng/src/vision/prompts/ocr_extraction.py:127-177` - OCR extraction prompt (детальный, 59 строк)
- `/home/liker/projects/telegram-signals-parisng/src/image_editing/openai_editor.py:227-253` - OpenAI `_build_prompt()` method
- `/home/liker/projects/telegram-signals-parisng/src/image_editing/gemini_editor.py:211-239` - Gemini `_build_prompt()` method

**Integration layer:**
- `/home/liker/projects/telegram-signals-parisng/src/ocr/image_editor.py` - Orchestration (Stage 1: OCR, Stage 2: Image Edit)
- `/home/liker/projects/telegram-signals-parisng/src/image_editing/factory.py` - Factory pattern для выбора редактора

**Тестовые данные:**
- `/home/liker/projects/telegram-signals-parisng/tests/data/mock_images/` - 4 PNG файла с торговыми сигналами

### 2. Codebase Analyzer (8 файлов проанализировано)

**Выявленные проблемы OCR промпта:**
- Избыточность (186 строк включая словарь терминов)
- Отсутствие приоритизации текста (торговые сигналы vs декоративный текст)
- Нет информации о позиционировании текста

**Критические проблемы OpenAI editor:**
1. **Неправильная маска** (`_create_mask()` строки 255-287): Создается полностью белая маска вместо прозрачной PNG с alpha-каналом
2. **Comma-separated формат**: Длинный список замен (`'A' to 'B', 'C' to 'D', ...`) теряет читаемость при >10 элементах
3. **Фиксированный размер 1024x1024**: Искажение пропорций для не-квадратных изображений
4. **Отсутствие контекста**: Не указано, что это торговый график

**Проблемы Gemini editor:**
- Лучше структурирован (bullet list с `\n`), но те же концептуальные проблемы
- Нет явного указания инвариантов

**Потеря информации между Stage 1 и Stage 2:**
- Stage 1 возвращает confidence, Stage 2 её игнорирует
- Низкоуверенные переводы обрабатываются так же, как высокоуверенные

### 3. Codebase Pattern Finder (5 паттернов)

**Найденные паттерны промптов:**

| Pattern | Качество | Пример файла |
|---------|----------|--------------|
| Детальный структурированный | 5/5 | `ocr_extraction.py` |
| Простой контекстный | 4/5 | `translators/openai.py` |
| Динамический comma-separated | 2/5 | `openai_editor.py` |
| Динамический bullet list | 3/5 | `gemini_editor.py` |
| Legacy OCR | 2/5 | `ocr/gemini_ocr.py` |

**Отсутствие тестов:**
- Нет unit-тестов для промптов
- Нет integration тестов для валидации качества
- Нет сравнительных тестов OpenAI vs Gemini

### 4. Web Search Researcher (25 источников)

**Критические находки:**

1. **Маски OpenAI**: Прозрачные пиксели (alpha=0) указывают области для редактирования, НЕ белые пиксели
2. **GPT-Image-1 vs DALL-E 2**: GPT-Image использует "soft mask" и может изменить всё изображение
3. **Структура промпта**: `[ДЕЙСТВИЕ] + [ЧТО СОХРАНИТЬ] + [ОГРАНИЧЕНИЯ]`
4. **Текст в кавычках**: Использовать `"OLD TEXT"` для литерального текста
5. **Явные инварианты**: Повторять что должно остаться неизменным в каждой итерации

**Рекомендуемый шаблон промпта:**
```
Replace the text "{old_text}" with "{new_text}" on this image.

PRESERVE COMPLETELY UNCHANGED:
- The exact font family, typeface, and weight
- The same font size and letter spacing
- The same text color, effects, and styling
- The exact position, alignment, and rotation
- All other text elements in the image
- The background, layout, and overall composition

REQUIREMENTS:
- Match the original typography precisely
- Do not add watermarks, logos, or any extra text
- Do not modify any other part of the image
```

---

## Solution Options

### Option 1: Quick Fix - Улучшение промптов (без изменения архитектуры)

**Описание:** Заменить текущие короткие промпты на детальные с явными инвариантами.

**Изменения:**
- `openai_editor.py:227-253` - Расширить `_build_prompt()` до 15-20 строк
- `gemini_editor.py:211-239` - Аналогичное расширение
- Добавить контекст "trading signal image" в оба промпта

**Pros:**
- Минимальные изменения кода (2 метода)
- Быстрая реализация (2-4 часа)
- Не ломает существующий API

**Cons:**
- Не исправляет проблему с маской OpenAI
- Не решает проблему потери confidence
- Не оптимизирует формат списка замен

**Effort:** Low (2-4 часа)
**Risk:** Low
**Expected Improvement:** 20-30%

---

### Option 2: Medium Fix - Исправление маски + улучшение промптов

**Описание:** Option 1 + исправление генерации маски с alpha-каналом + использование bullet list для OpenAI.

**Изменения:**
- `openai_editor.py:255-287` - Переписать `_create_mask()` для alpha-канала
- `openai_editor.py:244-246` - Использовать `\n` разделитель вместо `,`
- `openai_editor.py:227-253` - Детальный промпт с инвариантами
- `gemini_editor.py:211-239` - Детальный промпт с инвариантами
- Добавить параметр `quality="high"` в API вызов OpenAI

**Pros:**
- Исправляет критическую проблему с маской
- Улучшает читаемость промпта для LLM
- Не требует изменения интерфейсов

**Cons:**
- Требует тестирования на реальных изображениях
- Может увеличить время генерации (качество "high")

**Effort:** Medium (1-2 дня)
**Risk:** Medium
**Expected Improvement:** 40-60%

---

### Option 3: Full Fix - Полная переработка image editing модуля

**Описание:** Option 2 + передача confidence из OCR + опциональная маска только для текстовых областей + fallback стратегия.

**Изменения:**
- Все изменения из Option 2
- `src/ocr/image_editor.py:196-212` - Передавать confidence в Stage 2
- `openai_editor.py` - Добавить параметр `text_bboxes` для создания точной маски
- `base.py` - Расширить интерфейс `EditResult` для confidence
- `factory.py` - Добавить fallback с retry logic
- Добавить unit-тесты для промптов

**Pros:**
- Полное решение всех выявленных проблем
- Возможность создавать точные маски по bbox текста
- Фильтрация низкоуверенных переводов
- Покрытие тестами

**Cons:**
- Требует изменения интерфейсов (breaking changes)
- Требует OCR возвращать bounding boxes текста
- Значительный объем работы

**Effort:** High (3-5 дней)
**Risk:** Medium-High
**Expected Improvement:** 60-80%

---

## Recommended Approach

**Рекомендация: Option 2 (Medium Fix)**

**Обоснование:**
1. **Критичность маски**: Web-исследование показало, что белая маска - фундаментальная ошибка. Без исправления маски улучшения промптов дадут ограниченный эффект.
2. **Баланс effort/impact**: Option 2 исправляет 80% проблем за 20% усилий Option 3
3. **Низкий риск**: Не требует изменения интерфейсов, совместимо с текущим API
4. **Тестируемость**: Можно сравнить результаты до/после на существующих mock images

**Последовательность реализации:**
1. Исправить `_create_mask()` - критическая проблема
2. Переписать `_build_prompt()` для обоих редакторов
3. Изменить формат списка замен на bullet list
4. Протестировать на mock images
5. Опционально: реализовать части Option 3 в отдельном PR

---

## Files to Modify

| File | Change Type | Priority |
|------|-------------|----------|
| `/home/liker/projects/telegram-signals-parisng/src/image_editing/openai_editor.py` | Major rewrite of `_create_mask()` and `_build_prompt()` | Critical |
| `/home/liker/projects/telegram-signals-parisng/src/image_editing/gemini_editor.py` | Expand `_build_prompt()` with invariants | High |
| `/home/liker/projects/telegram-signals-parisng/src/vision/prompts/ocr_extraction.py` | Optional: add prioritization hints | Low |
| `/home/liker/projects/telegram-signals-parisng/tests/test_openai_integration.py` | Add prompt quality tests | Medium |

---

## Open Questions for User

1. **Приоритет исправления маски**: Маска - критическая проблема, но её исправление требует тестирования. Готовы ли выделить время на тестирование с реальными API вызовами?

2. **Выбор провайдера по умолчанию**: Текущий default - OpenAI. Web-исследование показало, что Gemini лучше сохраняет пропорции и поддерживает conversational editing. Рассмотреть смену default на Gemini?

3. **Bounding boxes для маски**: Для создания точной маски (только текстовые области) нужны координаты текста. Текущий OCR не возвращает bbox. Это приоритет для реализации?

4. **Фильтрация по confidence**: OCR возвращает confidence, но Stage 2 его игнорирует. Нужна ли фильтрация низкоуверенных переводов (< 0.8)?

5. **Тестирование**: Есть ли доступ к production API (OpenAI/Gemini) для тестирования изменений? Или только mock тесты?

---

## Patterns to Follow (from Pattern Finder)

**Для новых промптов использовать структуру OCR_EXTRACTION_PROMPT:**
1. **INSTRUCTIONS** - что делать
2. **OUTPUT FORMAT** - ожидаемый формат (не применимо для image editing, но можно указать REQUIREMENTS)
3. **RULES** - как делать, инварианты
4. **EXAMPLES** - если применимо
5. **SPECIAL CASES** - edge cases

**Параметры API:**
- `temperature=0` для детерминированного вывода
- `quality="high"` для продакшена (OpenAI)
- Явный запрос изображения: "Return the edited image"

---

## Metadata

```yaml
---
synthesized_from:
  - codebase-locator.md (32 files found)
  - codebase-analyzer.md (8 files analyzed, 12 symbols traced)
  - codebase-pattern-finder.md (5 patterns found)
  - web-search-researcher.md (25 sources cited)
options_count: 3
recommended_option: "Option 2: Medium Fix"
recommended_effort: "1-2 days"
recommended_risk: "Medium"
files_to_modify: 4
open_questions: 5
confidence: high
---
```
