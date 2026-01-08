# Tasks for: image-editing-prompts-quality

Generated: 2026-01-05 20:00:00
Total tasks: 6

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| Phase 1 | 2 | Fix image size/cropping |
| Phase 2 | 2 | Improve prompts |
| Phase 3 | 1 | Fix mask (optional) |
| Phase 4 | 1 | Test & validate |

## Task List

### task-01: analyze-openai-size-param

- **Phase**: 1
- **Type**: research
- **Risk**: low
- **Review**: false
- **Description**: Изучить текущий код OpenAI editor и понять как используется параметр size. Проверить документацию OpenAI API какие размеры поддерживаются для images.edit()
- **Files**:
  - `src/image_editing/openai_editor.py` (read)
- **Details**:
  - Найти где задаётся size="1024x1024"
  - Проверить поддерживаемые размеры в API
  - Определить можно ли не указывать size или нужен динамический расчёт
- **Depends on**: none
- **Blocks**: task-02
- **Agent**: codebase-analyzer
- **Verification**:
  - Найден код с size параметром
  - Понятны ограничения API
- **Status**: pending

---

### task-02: fix-openai-image-size

- **Phase**: 1
- **Type**: implement
- **Risk**: medium
- **Review**: true
- **Description**: Исправить параметр size в OpenAI editor чтобы сохранялись пропорции изображения
- **Files**:
  - `src/image_editing/openai_editor.py` (modify)
- **Details**:
  - Вариант A: Убрать параметр size (если API поддерживает)
  - Вариант B: Динамически вычислять ближайший поддерживаемый размер
  - Вариант C: Использовать размер входного изображения
  - Сохранить обратную совместимость
- **Depends on**: task-01
- **Blocks**: task-05
- **Agent**: implementer
- **Verification**:
  - Код компилируется без ошибок
  - Размер не хардкодится как 1024x1024
- **Status**: pending

---

### task-03: improve-openai-prompt

- **Phase**: 2
- **Type**: implement
- **Risk**: low
- **Review**: true
- **Description**: Переписать метод _build_prompt() в OpenAI editor с детальными инструкциями
- **Files**:
  - `src/image_editing/openai_editor.py` (modify)
- **Details**:
  - Добавить контекст "trading signal image"
  - Явно перечислить что сохранить (font, position, charts, price scale)
  - Явно перечислить что НЕ делать (watermarks, crop, resize)
  - Использовать bullet-list формат для замен вместо comma-separated
  - Добавить кавычки вокруг текста для замены
- **Depends on**: none
- **Blocks**: task-05
- **Agent**: implementer
- **Verification**:
  - Промпт содержит секции PRESERVE и DO NOT
  - Замены в формате `- "old" → "new"`
- **Status**: pending

---

### task-04: improve-gemini-prompt

- **Phase**: 2
- **Type**: implement
- **Risk**: low
- **Review**: false
- **Description**: Переписать метод _build_prompt() в Gemini editor аналогично OpenAI
- **Files**:
  - `src/image_editing/gemini_editor.py` (modify)
- **Details**:
  - Синхронизировать структуру промпта с OpenAI editor
  - Добавить секции PRESERVE и DO NOT
  - Добавить "Do not change aspect ratio"
  - Учесть особенности Gemini (он лучше сохраняет пропорции)
- **Depends on**: task-03
- **Blocks**: task-05
- **Agent**: implementer
- **Verification**:
  - Промпт аналогичен OpenAI по структуре
  - Содержит явные инварианты
- **Status**: pending

---

### task-05: manual-test-changes

- **Phase**: 4
- **Type**: test
- **Risk**: low
- **Review**: false
- **Description**: Протестировать изменения на реальных изображениях
- **Files**:
  - `scripts/compare_images.py` (use)
  - `data/image_comparison/` (output)
- **Details**:
  - Взять 3 изображения с SIZE MISMATCH из предыдущего анализа
  - Запустить через обновлённый editor
  - Сравнить размеры и качество
  - Документировать результат
- **Depends on**: task-02, task-03, task-04
- **Blocks**: task-06
- **Agent**: tester
- **Verification**:
  - Размеры совпадают или близки к оригиналу
  - Ценовая шкала не обрезана
  - Текст корректно заменён
- **Status**: pending

---

### task-06: fix-mask-optional

- **Phase**: 3
- **Type**: implement
- **Risk**: medium
- **Review**: true
- **Description**: (Опционально) Исправить генерацию маски с alpha-каналом или убрать маску
- **Files**:
  - `src/image_editing/openai_editor.py` (modify)
- **Details**:
  - Вариант A: Убрать маску полностью (GPT-Image-1 пересоздаёт изображение)
  - Вариант B: Создать маску с alpha-каналом (прозрачные пиксели = редактировать)
  - Решение зависит от результатов task-05
- **Depends on**: task-05
- **Blocks**: none
- **Agent**: implementer
- **Verification**:
  - Если маска убрана: код работает без маски
  - Если исправлена: PNG с правильным alpha-каналом
- **Status**: pending

---

## Dependency Graph

```
Phase 1 (Size):
  task-01 ──→ task-02 ──┐
                        │
Phase 2 (Prompts):      │
  task-03 ──→ task-04 ──┤
                        │
Phase 4 (Test):         ↓
                   task-05 ──→ task-06 (optional)
```

## Execution Batches

### Batch 1 (start - parallel)
- task-01: analyze size param
- task-03: improve OpenAI prompt

### Batch 2 (after batch 1)
- task-02: fix size (depends on task-01)
- task-04: improve Gemini prompt (depends on task-03)

### Batch 3 (after batch 2)
- task-05: manual testing

### Batch 4 (optional, after batch 3)
- task-06: fix mask (if needed)

## Verification Checklist

After all tasks complete:
- [ ] Выходные изображения сохраняют пропорции входных
- [ ] Ценовая шкала не обрезается
- [ ] Текст корректно заменяется
- [ ] Нет новых артефактов или искажений
- [ ] Код проходит существующие тесты
