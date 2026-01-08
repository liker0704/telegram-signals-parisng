# Task 04: Improve Gemini Prompt - IMPLEMENTATION COMPLETE

## Task
Переписать метод `_build_prompt()` в Gemini editor аналогично улучшенному OpenAI editor.

## Files Modified
- `/home/liker/projects/telegram-signals-parisng/src/image_editing/gemini_editor.py`: lines 211-256, переписан метод `_build_prompt()`

## Key Changes

### Before (old prompt format):
```python
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

### After (new structured prompt):
```python
replacements_list = "\n".join(
    f'- "{orig}" → "{trans}"'
    for orig, trans in translations.items()
)

return f"""This is a trading signal image. Replace the following text:

{replacements_list}

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
- Change the input aspect ratio
- Modify charts, indicators, or graphical elements
- Change colors, fonts, or styling
- Alter any text not explicitly listed for replacement
- Add or remove any visual elements

Replace ONLY the specified text while maintaining perfect visual consistency with the original image."""
```

### Changes Summary:
1. **Контекст**: Добавлен вводный контекст "This is a trading signal image"
2. **Формат замен**: Изменён с одинарных кавычек на двойные (`"old" → "new"`)
3. **Секция PRESERVE**: Добавлены явные инварианты с bullet-list
4. **Секция DO NOT**: Добавлены явные ограничения с bullet-list
5. **Gemini-специфичное**: Добавлено "Change the input aspect ratio" (Gemini лучше сохраняет пропорции, но нужно явно указать)
6. **Финальная инструкция**: Добавлена инструкция "Replace ONLY the specified text while maintaining perfect visual consistency"

## Verification Run
Command: `python3 -m py_compile src/image_editing/gemini_editor.py`
Result: Success (no syntax errors)
Syntax check: PASSED

## Status
SUCCESS

## Next Recommended Agent
tester

## Instructions for Tester
- Протестировать Gemini editor с новым промптом
- Сравнить результаты редактирования до и после изменений
- Проверить что Gemini:
  - Сохраняет пропорции изображения
  - Не добавляет watermark/logos
  - Заменяет только указанный текст
  - Сохраняет графики и индикаторы
- Запустить: `pytest tests/test_image_editing.py::test_gemini_editor -v`
- Ожидаемое поведение: Gemini должен выдавать более точные результаты с новым структурированным промптом

## For Dependents
- Изменения только в методе `_build_prompt()` класса `GeminiImageEditor`
- Публичный API не изменён
- Сигнатура метода осталась прежней: `_build_prompt(translations: Dict[str, str]) -> str`
- Новый промпт может увеличить качество редактирования

## Notes
- Промпт приведён в соответствие с улучшенным OpenAI editor
- Добавлена специфичная для Gemini инструкция про aspect ratio
- Структура промпта: контекст → замены → PRESERVE → DO NOT → финальная инструкция
- Формат кавычек изменён на двойные для единообразия с OpenAI
