# Implementation Plan: user-message-flow-tracking

Created: 2026-01-08 12:30:00
Status: draft
Based on: research/_summary.md

## Overview

Реализация отслеживания потока сообщений по пользователю с использованием двух механизмов:
1. **Simple Parent Check** — проверка `source_user_id` из БД в `update_handler.py`
2. **In-Memory TTL Tracker** — кэш активных потоков с автоматическим TTL

Это обеспечит:
- Быструю проверку через in-memory cache (O(1))
- Fallback на DB данные если cache miss
- Автоматическое освобождение потоков через TTL

## Goals

- Блокировать ответы на сигналы от пользователей, отличных от автора сигнала
- Минимизировать latency через in-memory кэширование
- Автоматически освобождать потоки через 72 часа неактивности
- Сохранить fallback на DB проверку

## Non-Goals

- Persistence потоков при рестарте (in-memory теряется, DB сохраняется)
- Возможность передачи потока другому пользователю
- Уведомление пользователей о заблокированных ответах
- Миграции БД

## Current State

- Фильтрация `SOURCE_ALLOWED_USERS` только для новых сигналов (`signal_handler.py:58-64`)
- `update_handler.py` НЕ проверяет sender_id — любой может отвечать
- `source_user_id` уже хранится в `signals` table
- Нет in-memory state для tracking

## Proposed Solution

### Hybrid: In-Memory Cache + DB Fallback

```
New Signal
    ↓
signal_handler.py
    ↓
start_flow(signal_id, user_id)  ← Register in cache
    ↓
[72 hour TTL]

Reply
    ↓
update_handler.py
    ↓
is_allowed(signal_id, user_id)  ← Check cache first
    ↓                               ↓
[Cache Hit]                    [Cache Miss]
    ↓                               ↓
Compare user_id             Check DB source_user_id
    ↓                               ↓
[Match → Allow]             [Match → Allow, Update cache]
[Mismatch → Reject]         [Mismatch → Reject]
```

## Implementation Phases

### Phase 1: Create Flow Tracker Module

**Goal**: Создать `src/state/flow_tracker.py` с TTL-based tracking

**Changes**:
- `src/state/__init__.py` (create)
- `src/state/flow_tracker.py` (create)

**Success Criteria**:
- Automated: `pytest tests/test_flow_tracker.py`
- Manual: Импорт модуля без ошибок

### Phase 2: Integrate in Signal Handler

**Goal**: Регистрировать flow при создании нового сигнала

**Changes**:
- `src/handlers/signal_handler.py`: Добавить `start_flow()` после успешного создания сигнала

**Success Criteria**:
- Automated: Existing tests pass
- Manual: Новые сигналы регистрируются в tracker

### Phase 3: Integrate in Update Handler

**Goal**: Проверять разрешение в update_handler с fallback на DB

**Changes**:
- `src/handlers/update_handler.py`: Добавить проверку `is_allowed()` + DB fallback

**Success Criteria**:
- Automated: `pytest tests/test_update_handler.py`
- Manual: Ответы от других пользователей игнорируются

### Phase 4: Add Unit Tests

**Goal**: Покрыть новый функционал тестами

**Changes**:
- `tests/test_flow_tracker.py` (create)
- `tests/test_update_handler.py` (modify if exists)

**Success Criteria**:
- Automated: `pytest tests/ -v`
- Manual: Coverage > 80% для нового кода

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Memory leak (no cleanup) | Medium | Medium | Periodic cleanup каждые 100 ops + TTL |
| Cache miss на первый reply | Low | Low | Fallback на DB check |
| Race condition в concurrent updates | Low | Low | Dict операции atomic в Python GIL |
| Lost flows при restart | Medium | Low | DB fallback всегда работает |

## Testing Strategy

### Automated Tests
- Unit tests: `flow_tracker.py` functions
- Integration tests: Signal creation → Flow start → Reply check
- Commands: `pytest tests/test_flow_tracker.py tests/test_update_handler.py`

### Manual Testing
- Создать сигнал от User A
- Ответить от User A → должен пройти
- Ответить от User B → должен быть проигнорирован
- Подождать 1 час → ответ от User B должен пройти (TTL expired)

## Rollback Plan

1. Удалить вызовы `start_flow()` и `is_allowed()` из handlers
2. Удалить `src/state/` directory
3. Удалить `tests/test_flow_tracker.py`
4. Откатить `update_handler.py` к предыдущей версии

## Files Summary

| File | Action | Phase |
|------|--------|-------|
| `src/state/__init__.py` | Create | 1 |
| `src/state/flow_tracker.py` | Create | 1 |
| `src/handlers/signal_handler.py` | Modify | 2 |
| `src/handlers/update_handler.py` | Modify | 3 |
| `tests/test_flow_tracker.py` | Create | 4 |
