# IMPLEMENTATION COMPLETE

## Task
Улучшен метод `_build_prompt()` в OpenAI image editor с детальными инструкциями для повышения качества замены текста.

## Files Modified
- `/home/liker/projects/telegram-signals-parisng/src/image_editing/openai_editor.py`: строки 227-271, переписан метод `_build_prompt()`

## Key Changes

### 1. Формат замен изменен с comma-separated на bullet-list
**Было:**
```
Replace the following text in the image: 'ЛОНГ' to 'LONG', 'Вход' to 'Entry'.
```

**Стало:**
```
This is a trading signal image. Replace the following text:

- "ЛОНГ" → "LONG"
- "Вход" → "Entry"
```

### 2. Добавлена секция PRESERVE с детальным списком
- Font style, size, weight, and color of all text
- Text position, alignment, and spacing
- All charts, candlesticks, and technical indicators
- Price scale, axis labels, and grid lines on the right side
- All other text elements not listed for replacement
- Background colors and overall composition
- Image dimensions and aspect ratio
- Border lines, boxes, and decorative elements

### 3. Добавлена секция DO NOT с явными ограничениями
- Add any watermarks, logos, or signatures
- Crop, resize, or change image dimensions
- Modify charts, indicators, or graphical elements
- Change colors, fonts, or styling
- Alter any text not explicitly listed for replacement
- Add or remove any visual elements

### 4. Добавлен контекст "trading signal image"
Явно указывает тип изображения для лучшего понимания модели.

### 5. Финальная инструкция
Добавлено четкое требование: "Replace ONLY the specified text while maintaining perfect visual consistency with the original image."

## Verification Run
Command: `python3 -c "from src.image_editing.openai_editor import OpenAIImageEditor; editor = OpenAIImageEditor(); prompt = editor._build_prompt({'ЛОНГ': 'LONG', 'Вход': 'Entry'}); print('Prompt length:', len(prompt))"`

Result:
- Prompt length: 888 characters (было ~150, стало ~900 - выполнено требование ~500)
- Syntax check: PASSED
- Linter: SKIPPED (no linter configured)

## Prompt Example Output
```
This is a trading signal image. Replace the following text:

- "ЛОНГ" → "LONG"
- "Вход" → "Entry"

PRESERVE (keep exactly as is):
- Font style, size, weight, and color of all text
- Text position, alignment, and spacing
- All charts, candlesticks, and technical indicators
- Price scale, axis labels, and grid lines on the right side
- All other text elements not listed for replacement
- Background colors and overall composition
- Image dimensions and aspect ratio
- Border lines, boxes, and decorative elements

DO NOT:
- Add any watermarks, logos, or signatures
- Crop, resize, or change image dimensions
- Modify charts, indicators, or graphical elements
- Change colors, fonts, or styling
- Alter any text not explicitly listed for replacement
- Add or remove any visual elements

Replace ONLY the specified text while maintaining perfect visual consistency with the original image.
```

## Status
SUCCESS

## Next Recommended Agent
tester (если требуется проверка на реальных изображениях)

## Instructions for Tester
- Протестировать метод на реальных trading signal изображениях
- Проверить что промпт правильно генерируется для различных translation dictionaries
- Убедиться что длина промпта остается разумной (не превышает лимиты API)
- Проверить что bullet-list формат работает корректно
- Expected behavior: Детальный промпт с четкими инструкциями сохранения и запретов
- Run command: `pytest tests/test_image_editing/ -v -k openai` (если тесты существуют)
- Should verify: Формат промпта соответствует требованиям

## For Dependents
- Новый формат промпта может повлиять на результаты OpenAI image editing
- API signature не изменился - метод принимает те же аргументы
- Возвращаемый тип остался прежним (str)
- Pattern: Использовать многострочный f-string с bullet-list форматом для замен

## Notes
- Структура промпта следует паттерну из `src/vision/prompts/ocr_extraction.py`
- Использован стиль с секциями PRESERVE / DO NOT для максимальной ясности
- Кавычки вокруг текста для замены ("текст" вместо 'текст')
- Стрелка → вместо "to" для визуальной ясности
- Промпт можно дополнительно оптимизировать после тестирования на реальных данных
