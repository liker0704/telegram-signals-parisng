# Research Synthesis: User Message Flow Tracking

## Executive Summary

Система обрабатывает торговые сигналы из Telegram и пересылает их в target-группу, но **фильтрация пользователей применяется только к новым сигналам** (`#Идея`), а не к ответам. Любой пользователь может отвечать на сигнал любого другого пользователя, что противоречит ожидаемому поведению "поток сообщений привязан к автору". Решение требует добавления проверки `source_user_id` в `update_handler.py` или внедрения отдельного flow tracker.

---

## Key Discoveries from Each Agent

### 1. Codebase Locator
**Files found: 35 | Confidence: high**

- **Entry point**: `src/main.py:78-108` - регистрация обработчика `@reader_client.on(events.NewMessage)`
- **Signal handler**: `src/handlers/signal_handler.py:23` - единственное место фильтрации пользователей (lines 58-64)
- **Update handler**: `src/handlers/update_handler.py:27` - **НЕТ фильтрации пользователей**
- **Database**: `source_user_id` уже хранится в `signals` и `signal_updates`, но **не используется для бизнес-логики**
- **Config**: `SOURCE_ALLOWED_USERS` парсится в `config.py:289-310`

### 2. Codebase Analyzer
**Files analyzed: 6 | Confidence: high**

- **Threading mechanism**: Telethon `reply_to_msg_id` → DB lookup → Target `reply_to` parameter
- **Critical gap**: В `update_handler.py` нет проверки `sender_id` вообще - поле только записывается в БД (line 98)
- **Missing check** (suggested):
  ```python
  if parent_signal['source_user_id'] != message.sender_id:
      logger.debug("Reply from different user, ignoring")
      return
  ```
- **No in-memory state**: Все состояние в PostgreSQL, нет кэширования

### 3. Codebase Pattern Finder
**Patterns found: 8 | Confidence: high**

- **Global state pattern**: `_pool`, `_reader_client`, `_running_tasks` - module-level variables с `Optional[]`
- **User validation pattern**: Early return с `logger.debug()` для отклоненных сообщений
- **Idempotency pattern**: Check `db_find_*_by_source_msg()` в начале каждого handler
- **Frozenset for whitelists**: `ALLOWED_SIGNAL_COLUMNS` в `queries.py`
- **Tracked tasks**: `create_tracked_task()` для async task management

### 4. Web Search Researcher
**Sources consulted: 45 | Confidence: high**

- **Telegram threads**: `reply_to_top_id` = thread ID, равен ID оригинального сообщения
- **TTL approaches**: cachetools TTLCache, custom dict, Redis - в порядке возрастающей сложности
- **Best practice**: Start с in-memory, migrate на Redis при необходимости scaling
- **contextvars**: Современный паттерн для per-task state, но overkill для данного use case
- **Recommended TTL**: 30-60 минут для активных conversation flows

---

## Solution Options

### Option 1: Simple Parent Check (Minimal Change)

**Description**: Добавить проверку `source_user_id` в `update_handler.py` после lookup parent signal.

**Changes**:
```python
# update_handler.py:79 (after finding parent_signal)
if parent_signal.get('source_user_id') != message.sender_id:
    logger.debug("Reply from different user than signal author, ignoring",
                signal_id=parent_signal['id'],
                sender_id=message.sender_id,
                signal_author=parent_signal.get('source_user_id'))
    return
```

| Aspect | Value |
|--------|-------|
| **Effort** | Low (~30 min) |
| **Risk** | Very Low |
| **Files to modify** | 1 (`update_handler.py`) |
| **Testing needed** | Unit test + manual |

**Pros**:
- Минимальные изменения
- Использует существующие данные в БД
- Легко откатить

**Cons**:
- Нет явного "flow" концепта
- Нельзя передать поток другому пользователю
- При каждом reply делается DB query (уже делается, не добавляет overhead)

---

### Option 2: In-Memory Flow Tracker

**Description**: Создать модуль `src/state/flow_tracker.py` с TTL-based tracking активных потоков.

**Changes**:
```python
# src/state/flow_tracker.py (new file)
from typing import Dict, Optional
import time

_active_flows: Dict[int, tuple[int, float]] = {}  # signal_id -> (user_id, timestamp)
FLOW_TTL = 3600  # 1 hour

def start_flow(signal_id: int, user_id: int) -> None:
    _active_flows[signal_id] = (user_id, time.time())

def is_user_allowed(signal_id: int, user_id: int) -> bool:
    if signal_id not in _active_flows:
        return True
    owner_id, timestamp = _active_flows[signal_id]
    if time.time() - timestamp > FLOW_TTL:
        del _active_flows[signal_id]
        return True
    return owner_id == user_id
```

| Aspect | Value |
|--------|-------|
| **Effort** | Medium (~2 hours) |
| **Risk** | Low |
| **Files to modify** | 3 (`signal_handler.py`, `update_handler.py`, new `flow_tracker.py`) |
| **Testing needed** | Unit tests for tracker + integration |

**Pros**:
- Явная концепция "flow"
- Быстрая проверка (O(1), no DB)
- TTL автоматически освобождает потоки
- Можно добавить функционал передачи потока

**Cons**:
- Lost при рестарте (можно добавить persistence позже)
- Дублирование информации (DB + memory)
- Память растет с количеством активных потоков

---

### Option 3: Database Column + Index

**Description**: Добавить колонку `active_flow_user_id` в таблицу `signals` и индекс для быстрого поиска.

**Changes**:
```sql
-- migrations/003_add_flow_tracking.sql
ALTER TABLE signals
ADD COLUMN active_flow_user_id BIGINT,
ADD COLUMN flow_started_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX idx_signals_active_flow
ON signals(active_flow_user_id)
WHERE active_flow_user_id IS NOT NULL;
```

| Aspect | Value |
|--------|-------|
| **Effort** | Medium-High (~3-4 hours) |
| **Risk** | Medium (migration) |
| **Files to modify** | 4 (migration, `queries.py`, `signal_handler.py`, `update_handler.py`) |
| **Testing needed** | Migration test + handlers |

**Pros**:
- Persistent - survives restarts
- Single source of truth
- Можно запросить статистику по flows

**Cons**:
- Migration risk
- Дополнительная нагрузка на DB
- Overkill если не нужен persistence

---

## Recommended Approach

### Option 1: Simple Parent Check

**Rationale**:
1. **Минимальный риск**: Одна проверка в одном файле, легко откатить
2. **Использует существующие данные**: `source_user_id` уже хранится в БД
3. **Достаточно для требований**: Блокирует ответы от "чужих" пользователей
4. **Следует существующим паттернам**: Early return с `logger.debug()`, как в `signal_handler.py`
5. **Быстро реализовать**: ~30 минут с тестами

**Эволюция**: Если потребуется TTL или transfer ownership - можно перейти на Option 2 позже.

---

## Files to Modify

| File | Change Type | Priority |
|------|-------------|----------|
| `src/handlers/update_handler.py` | Add user validation check after line 78 | **Required** |
| `tests/test_update_handler.py` | Add test for user filtering (if exists) | Recommended |

### Exact Insertion Point

```python
# src/handlers/update_handler.py:78-79 (current)
if not parent_signal.get('target_message_id'):
    logger.warning("Parent signal was not posted to target", ...)
    return

# INSERT HERE (after line 84, before line 85)
# Check if sender matches signal author (flow tracking)
if config.allowed_users_list:  # Only if filtering enabled
    signal_author = parent_signal.get('source_user_id')
    if signal_author and signal_author != message.sender_id:
        logger.debug("Update from different user than signal author, ignoring",
                    signal_id=parent_signal['id'],
                    sender_id=message.sender_id,
                    signal_author=signal_author)
        return
```

---

## Patterns to Follow

From pattern-finder report:

1. **Early return pattern** (signal_handler.py:58-64):
   ```python
   if condition:
       logger.debug("Reason for rejection", extra_fields...)
       return
   ```

2. **Config check wrapper** (signal_handler.py:58):
   ```python
   if config.allowed_users_list:  # Only validate if configured
       # validation logic
   ```

3. **Dict .get() for optional fields** (update_handler.py:78):
   ```python
   if not parent_signal.get('target_message_id'):
   ```

4. **Debug logging for expected rejections** (not error/warning):
   ```python
   logger.debug("Update from different user", sender_id=..., signal_author=...)
   ```

---

## Open Questions for User

1. **Scope of filtering**: Должна ли проверка применяться только когда `SOURCE_ALLOWED_USERS` настроен, или всегда?
   - Current recommendation: только если `config.allowed_users_list` не пустой

2. **Behavior for old signals**: Что делать с сигналами без `source_user_id` (созданными до этой фичи)?
   - Current recommendation: разрешать ответы (fallback to allow)

3. **TTL requirement**: Нужен ли автоматический "release" потока через N минут неактивности?
   - Current recommendation: не нужен для MVP (DB данные постоянны)

4. **Notification**: Нужно ли уведомлять пользователя, что его ответ был проигнорирован?
   - Current recommendation: silent ignore (как текущее поведение для unauthorized signals)

---

## Conflicts Between Agents

**None identified**. Все агенты согласны:
- Проблема в `update_handler.py` (нет проверки sender_id)
- `source_user_id` уже хранится в БД
- Решение: добавить проверку после lookup parent signal

---

## Gaps in Research

1. **Testing coverage**: Нет информации о существующих тестах для `update_handler.py`
2. **Edge cases**: Не исследованы: deleted messages, edited signals, group migrations
3. **Performance**: Не измерено влияние дополнительной проверки (ожидается незначительное)

---

```yaml
---
status: SUCCESS
agents_synthesized: 4
options_identified: 3
recommended: Option 1 (Simple Parent Check)
files_affected: 1-2
open_questions: 4
confidence: high
---
```
