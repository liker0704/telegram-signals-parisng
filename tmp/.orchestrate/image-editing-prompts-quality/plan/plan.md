# Implementation Plan: image-editing-prompts-quality

Created: 2026-01-05 20:00:00
Status: approved
Based on: research/_summary.md + visual analysis of 12 image pairs

## Overview

Исправление критических проблем с image editing для торговых сигналов. Визуальный анализ 12 пар изображений показал:
- **7 из 12** имеют критическую обрезку до квадрата 1024x1024
- **5 из 12** идентичны оригиналу (перевод не требовался)
- OCR ошибки: "TradingView" → "Trealingvcom", даты искажаются

## Goals

1. Сохранять оригинальные пропорции изображений (не обрезать до квадрата)
2. Улучшить качество замены текста (сохранение шрифтов, позиций)
3. Минимизировать потерю информации (ценовая шкала, заголовки, индикаторы)

## Non-Goals

- Изменение OCR пайплайна (отдельная задача)
- Добавление bounding boxes для текста (требует изменения OCR)
- Смена провайдера по умолчанию

## Current State

```
openai_editor.py:
- size="1024x1024"  # ЖЁСТКО КВАДРАТ → обрезка
- mask = белая (255,255,255,255)  # НЕПРАВИЛЬНО
- prompt = 2-3 предложения  # СЛИШКОМ КРАТКО
```

## Proposed Solution

### Главное изменение: Убрать принудительный квадрат

**Проблема**: `size="1024x1024"` обрезает прямоугольные изображения.

**Решение**:
- Для GPT-Image-1: НЕ указывать size (API сохранит пропорции)
- Альтернатива: Вычислять ближайший поддерживаемый размер с сохранением пропорций

### Улучшение промптов

**Текущий промпт** (~40 символов):
```
Replace the following text on the image: 'X' to 'Y'.
Preserve formatting.
```

**Новый промпт** (~500 символов):
```
Replace the text "{old}" with "{new}" on this trading signal image.

PRESERVE COMPLETELY UNCHANGED:
- Font style, size, weight, and color
- Text position and alignment
- All charts, candlesticks, and indicators
- Price scale on the right side
- All other text elements
- Background and overall composition
- Image dimensions and aspect ratio

DO NOT:
- Add watermarks or logos
- Crop or resize the image
- Modify charts or indicators
- Change any text not listed above
```

## Implementation Phases

### Phase 1: Fix Image Size (Critical)

**Goal**: Убрать обрезку до квадрата

**Changes**:
- `src/image_editing/openai_editor.py`: Убрать `size="1024x1024"` или сделать динамическим

**Success Criteria**:
- Выходное изображение сохраняет пропорции входного
- Manual: Проверить на тестовом изображении 1280x720

### Phase 2: Improve Prompts

**Goal**: Детальные промпты с инвариантами

**Changes**:
- `src/image_editing/openai_editor.py`: Переписать `_build_prompt()`
- `src/image_editing/gemini_editor.py`: Переписать `_build_prompt()`

**Success Criteria**:
- Промпт содержит явные инструкции по сохранению
- Список замен в bullet-list формате

### Phase 3: Fix Mask (Optional)

**Goal**: Правильная маска с alpha-каналом

**Changes**:
- `src/image_editing/openai_editor.py`: Переписать `_create_mask()`

**Note**: Для GPT-Image-1 маска менее критична (он пересоздаёт изображение).
Можно попробовать без маски вообще.

### Phase 4: Test & Validate

**Goal**: Проверить на реальных изображениях

**Changes**:
- Запустить на 5 тестовых сигналах
- Сравнить до/после

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OpenAI API не поддерживает произвольные размеры | Medium | High | Проверить документацию, fallback на ресайз |
| Качество хуже с новыми промптами | Low | Medium | A/B тест, rollback |
| Увеличение стоимости API | Low | Low | Мониторинг usage |

## Testing Strategy

### Manual Testing
1. Взять 3 изображения с SIZE MISMATCH из анализа
2. Применить изменения
3. Сравнить результат визуально

### Automated (Future)
- Проверка размеров выходного изображения
- Проверка что текст изменился

## Rollback Plan

1. `git revert` коммита с изменениями
2. Промпты не влияют на другой код - изолированы
