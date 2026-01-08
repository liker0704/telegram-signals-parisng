# Расположение кода для Image Editing / Обработки изображений

## Основные файлы с промптами

### Image Editing Prompts (редактирование изображений)

#### 1. **OpenAI Image Editor Prompts**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/image_editing/openai_editor.py`
- **Метод**: `_build_prompt()` (строки 227-253)
- **Промпты**:
  - Без переводов: "Translate all Russian text in this image to English. Preserve the original formatting, colors, and layout exactly."
  - С переводами: "Replace the following text in the image: {replacements}. Preserve the original formatting, colors, fonts, and layout exactly. Keep all other elements unchanged."
  - Формат замен: `'original' to 'translation'` (через запятую)

#### 2. **Gemini Image Editor Prompts**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/image_editing/gemini_editor.py`
- **Метод**: `_build_prompt()` (строки 211-239)
- **Промпты**:
  - Без переводов: "Translate all Russian text in this image to English. Preserve the original formatting, colors, and layout. Return the edited image with English text."
  - С переводами: "Edit this image by replacing the following text:\n\n{replacements}\n\nPreserve the original formatting, colors, fonts, and layout exactly. Keep all other elements of the image unchanged. Return the edited image with the text replaced."
  - Формат замен: `- 'original' → 'translation'` (построчно с переносами)

### OCR Extraction Prompts (извлечение текста из изображений)

#### 3. **Vision OCR Prompt**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/vision/prompts/ocr_extraction.py`
- **Константа**: `OCR_EXTRACTION_PROMPT` (строки 127-177)
- **Назначение**: Извлечение и перевод текста из торговых графиков
- **Ключевые инструкции**:
  - Найти весь видимый текст (русский, английский, кириллица)
  - Перевести русский текст на английский
  - Сохранить форматирование чисел, символов валют, процентов
  - Формат вывода: `ORIGINAL: [text] -> ENGLISH: [translation]`
  - Специальная терминология трейдинга (ЛОНГ→LONG, ШОРТ→SHORT, Вход→Entry, etc.)

## Файлы реализации Image Editing

### Core Implementation

#### 4. **Base Image Editor (абстракция)**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/image_editing/base.py`
- **Класс**: `ImageEditor` (ABC)
- **Методы**:
  - `edit_image()` - синхронное редактирование
  - `edit_image_async()` - асинхронное редактирование
- **Датакласс**: `EditResult` (результат редактирования)

#### 5. **OpenAI Image Editor**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/image_editing/openai_editor.py`
- **Класс**: `OpenAIImageEditor`
- **API**: OpenAI `images.edit()` endpoint (строка 129)
- **Особенности**:
  - Использует маску (полная белая маска - редактирует все изображение)
  - Метод `_create_mask()` (строки 255-290)
  - Модель: `gpt-image-1` (по умолчанию)

#### 6. **Gemini Image Editor**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/image_editing/gemini_editor.py`
- **Класс**: `GeminiImageEditor`
- **API**: Gemini Vision API с промптом для редактирования
- **Модель**: `gemini-2.5-flash-image` (по умолчанию)
- **Особенности**: Отправляет всё изображение с промптом (без маски)

#### 7. **Image Editor Factory**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/image_editing/factory.py`
- **Класс**: `ImageEditorFactory`
- **Методы**:
  - `get_editor(name)` - получить редактор по имени
  - `get_editor_with_fallback()` - с автоматическим fallback
  - `register()` - регистрация кастомных редакторов
  - `list_available_editors()` - список доступных редакторов
- **Поддерживаемые провайдеры**: `openai`, `gemini`

#### 8. **Module Exports**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/image_editing/__init__.py`
- **Экспорты**: `ImageEditor`, `EditResult`, `ImageEditorFactory`, `GeminiImageEditor`, `OpenAIImageEditor`

### Integration Layer

#### 9. **OCR Image Editor (точка интеграции)**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/ocr/image_editor.py`
- **Функции**:
  - `edit_image_text_sync()` (строка 156) - синхронная обработка
  - `edit_image_text()` (строка 253) - асинхронная обработка
- **Процесс**:
  - Stage 1: Vision OCR извлекает и переводит текст
  - Stage 2: Image Editor генерирует новое изображение с переводами
- **Использует**: `ImageEditorFactory.get_editor_with_fallback()` (строка 219)

#### 10. **OCR Module Exports**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/ocr/__init__.py`
- **Экспорт**: `edit_image_text` (публичный API)

## Vision Providers (для OCR extraction)

### Vision Provider Implementations

#### 11. **Gemini Vision Provider**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/vision/providers/gemini.py`
- **Использует**: `OCR_EXTRACTION_PROMPT` (строка 289)

#### 12. **OpenAI Vision Provider**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/vision/providers/openai.py`
- **Использует**: `OCR_EXTRACTION_PROMPT` (строки 193, 202)

#### 13. **Anthropic Vision Provider**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/vision/providers/anthropic.py`
- **Использует**: `OCR_EXTRACTION_PROMPT` (строки 193, 202)

#### 14. **Vision Prompts Module**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/vision/prompts/__init__.py`
- **Экспорт**: `OCR_EXTRACTION_PROMPT`

## Конфигурация

#### 15. **Config Settings**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/config.py`
- **Параметры Image Editing**:
  - `IMAGE_EDITOR` (строка 117): провайдер редактирования (gemini/openai)
  - `IMAGE_EDITOR_FALLBACK` (строка 121): резервный провайдер
  - `OPENAI_IMAGE_MODEL` (строка 125): модель OpenAI для редактирования
  - `GEMINI_IMAGE_MODEL` (строка 65): модель Gemini для редактирования
- **Параметры Vision OCR**:
  - `VISION_PROVIDER` (строка 100): провайдер OCR (gemini/openai/anthropic)
  - `GEMINI_MODEL` (строка 61): модель Gemini для OCR
  - `OPENAI_VISION_MODEL` (строка 75): модель OpenAI для OCR
  - `ANTHROPIC_VISION_MODEL` (строка 93): модель Claude для OCR

#### 16. **Environment Example**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/.env.example`
- **Настройки** (строки 97-106):
  - `IMAGE_EDITOR=openai` (рекомендуется)
  - `IMAGE_EDITOR_FALLBACK=gemini`
  - `OPENAI_IMAGE_MODEL=gpt-image-1`

## Тесты

#### 17. **OpenAI Integration Tests**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/tests/test_openai_integration.py`
- **Тесты**:
  - `TestImageEditorModule` (класс, строка 248)
  - `test_import_edit_image_text()` (строка 99)
  - Проверки наличия `edit_image_text` и `edit_image_text_sync`

## Примеры изображений

### Test Data / Mock Images

#### 18. **Mock Signal Images**
- **Директория**: `/home/liker/projects/telegram-signals-parisng/tests/data/mock_images/`
- **Файлы**:
  - `signal_ocr_1.png` - тестовое изображение сигнала #1
  - `signal_ocr_2.png` - тестовое изображение сигнала #2
  - `signal_ocr_3.png` - тестовое изображение сигнала #3
  - `signal_russian_only.png` - изображение только с русским текстом

#### 19. **Test Dataset JSON**
- **Файлы**:
  - `/home/liker/projects/telegram-signals-parisng/tests/data/integration_test_signals.json`
  - `/home/liker/projects/telegram-signals-parisng/tests/data/test_dataset_signals.json`

### Image Generation Scripts

#### 20. **Mock Image Generator**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/scripts/generate_mock_images.py`
- **Назначение**: Генерация тестовых изображений торговых сигналов с русским текстом
- **Функция**: `generate_signal_image()` (строка 243)

#### 21. **Russian Test Image Generator**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/scripts/generate_russian_test_image.py`
- **Назначение**: Генерация тестового изображения только с русским текстом

## Документация

#### 22. **Architecture Decision Records**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/docs/architecture/adr-0001-multi-provider-vision.md`
- **Содержит**: Архитектура multi-provider vision и image editing

#### 23. **Research: Image-Text Translation Analysis**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/docs/research/image-text-translation-analysis.md`
- **Содержит**: Анализ подходов к переводу текста на изображениях

#### 24. **Research: Low-Res Seamless Text**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/docs/research/low-res-seamless-text.md`
- **Содержит**: Исследование работы с low-resolution текстом

#### 25. **Research: Implementation Reference**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/docs/research/implementation-ref.md`
- **Содержит**: Справочник по реализации

#### 26. **Research README**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/docs/research/README.md`
- **Содержит**: Обзор research материалов

#### 27. **Integration Testing Guide**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/docs/INTEGRATION_TESTING.md`
- **Содержит**: Инструкции по интеграционному тестированию, включая генерацию изображений

#### 28. **Testing Report**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/TESTING_REPORT.md`
- **Содержит**: Результаты тестирования image editor функций

## Memory / Analysis

#### 29. **Serena Memory: Image Editing Architecture**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/.serena/memories/image_editing_architecture_analysis.md`
- **Содержит**: Анализ архитектуры image editing, включая неиспользуемые компоненты

#### 30. **Orchestration Task**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/tmp/.orchestrate/image-editing-prompts-quality/task.md`
- **Содержит**: Текущая задача по анализу качества промптов

## Handlers (использование image editing)

#### 31. **Signal Handler**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/handlers/signal_handler.py`
- **Использует**: image editing через OCR модуль

#### 32. **Update Handler**
- **Файл**: `/home/liker/projects/telegram-signals-parisng/src/handlers/update_handler.py`
- **Использует**: image editing через OCR модуль

## Директории по назначению

### Implementation Files (8 файлов)
- `/home/liker/projects/telegram-signals-parisng/src/image_editing/` - 5 файлов (base, openai_editor, gemini_editor, factory, __init__)
- `/home/liker/projects/telegram-signals-parisng/src/vision/prompts/` - 2 файла (ocr_extraction, __init__)
- `/home/liker/projects/telegram-signals-parisng/src/ocr/image_editor.py` - 1 файл (integration layer)

### Test Files (1 файл)
- `/home/liker/projects/telegram-signals-parisng/tests/test_openai_integration.py`

### Mock/Test Images (4 файла PNG)
- `/home/liker/projects/telegram-signals-parisng/tests/data/mock_images/` - содержит 4 PNG файла

### Configuration Files (2 файла)
- `/home/liker/projects/telegram-signals-parisng/src/config.py`
- `/home/liker/projects/telegram-signals-parisng/.env.example`

### Documentation Files (6 файлов)
- `/home/liker/projects/telegram-signals-parisng/docs/research/` - 4 MD файла
- `/home/liker/projects/telegram-signals-parisng/docs/architecture/adr-0001-multi-provider-vision.md`
- `/home/liker/projects/telegram-signals-parisng/docs/INTEGRATION_TESTING.md`

### Scripts (2 файла)
- `/home/liker/projects/telegram-signals-parisng/scripts/generate_mock_images.py`
- `/home/liker/projects/telegram-signals-parisng/scripts/generate_russian_test_image.py`

## Entry Points

### Публичные API
1. **OCR Module**: `from src.ocr import edit_image_text` - главная точка входа для редактирования изображений
2. **Image Editing Module**: `from src.image_editing import ImageEditorFactory` - фабрика редакторов
3. **Vision Prompts**: `from src.vision.prompts import OCR_EXTRACTION_PROMPT` - промпт для OCR

### Использование в коде
- `src/ocr/gemini_ocr.py` (строка 137): импортирует `edit_image_text`
- `src/handlers/signal_handler.py`: использует image editing через OCR
- `src/handlers/update_handler.py`: использует image editing через OCR

## Naming Patterns

### Промпты
- Константы: `OCR_EXTRACTION_PROMPT`, `*_PROMPT`
- Методы: `_build_prompt()` (приватный метод в редакторах)

### Редакторы
- Классы: `*ImageEditor` (OpenAIImageEditor, GeminiImageEditor)
- Методы: `edit_image()`, `edit_image_async()`
- Функции: `edit_image_text()`, `edit_image_text_sync()`

### Конфигурация
- Переменные: `IMAGE_EDITOR`, `*_MODEL`, `*_IMAGE_MODEL`

---
status: SUCCESS
files_found: 32
categories:
  implementation: 8
  tests: 1
  config: 2
  docs: 6
  types: 0
  mock_images: 4
  scripts: 2
  memory: 1
  handlers: 2
  task_files: 1
  test_data: 2
  reports: 3
confidence: high
---
