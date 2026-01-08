# Codebase Analysis: Message Flow and User Tracking

## Overview

Система обрабатывает торговые сигналы из Telegram-группы в двух режимах:
1. **Новый сигнал** (с маркером `#Идея`) - создает новую запись в таблице `signals`
2. **Ответ на сигнал** (reply to existing message) - создает запись в `signal_updates`, привязанную к родительскому сигналу

Фильтрация пользователей выполняется **только для новых сигналов** через `SOURCE_ALLOWED_USERS`, но не отслеживается на уровне потока ответов. Нет механизма "активного пользователя потока" - система обрабатывает все ответы от любых пользователей, если родительское сообщение является сигналом.

---

## Entry Points

### Main Event Handler Registration
**File:** `src/main.py:78-108`

```python
@reader_client.on(events.NewMessage(chats=[config.SOURCE_GROUP_ID], incoming=True, outgoing=True))
async def on_new_message(event):
```

- **Слушает:** Все новые сообщения из `SOURCE_GROUP_ID`
- **Фильтр уровня Telethon:** `incoming=True, outgoing=True` - принимает сообщения от других и от самого reader account
- **Роутинг:**
  - Если `is_signal(text)` (содержит `#Идея`) → `handle_new_signal()` (line 99)
  - Если `message.is_reply` → `handle_signal_update()` (line 102)
  - Иначе → игнорируется

---

## Core Implementation

### 1. Signal Detection (`src/parsers/signal_parser.py:9-21`)

#### Function: `is_signal(text: str) -> bool`
- **Логика:** Проверяет наличие `#идея` в тексте (case-insensitive)
- **Return:** `True` если найден маркер, иначе `False`
- **Используется:** В `main.py:97` для роутинга нового сигнала

```python
def is_signal(text: str) -> bool:
    if not text:
        return False
    return '#идея' in text.lower()
```

---

### 2. New Signal Handler (`src/handlers/signal_handler.py:23-220`)

#### Entry Point: `handle_new_signal(event: NewMessage.Event)`

#### User Filtering (lines 58-64)
**КРИТИЧНО:** Единственное место, где фильтруется пользователь

```python
if config.allowed_users_list:
    sender_id = message.sender_id
    if sender_id not in config.allowed_users_list:
        logger.debug("Signal from unauthorized user, ignoring", sender_id=sender_id)
        return  # EXIT - сообщение игнорируется
```

- **Config:** `config.allowed_users_list` парсится из `SOURCE_ALLOWED_USERS` (comma-separated integers)
- **Behavior:** Если список не пуст и `sender_id` не в списке → **silent ignore**
- **No tracking:** Нет сохранения информации о том, что пользователь начал поток

#### Database Flow
1. **Create initial record** (lines 71-80):
   - Вставляет в таблицу `signals`
   - Поля: `source_chat_id`, `source_message_id`, `source_user_id` (message.sender_id), `original_text`
   - Статус: `PENDING`
   - **Возвращает:** `signal_id` (SERIAL PRIMARY KEY)

2. **Update status to PROCESSING** (line 83)

3. **Parse trading fields** (lines 86-97):
   - Извлекает pair, direction, timeframe, entry_range, tp1-tp3, sl, risk_percent
   - Обновляет запись в БД

4. **Media processing** (lines 100-110)

5. **Translation & forwarding** (lines 113-148)

6. **Post to target group** (lines 164-176)

7. **Update DB with result** (lines 184-193):
   - `target_chat_id`, `target_message_id` - **ключевые поля для threading**
   - `forward_chat_id`, `forward_message_id` - для параллельного форварда
   - `status`: `POSTED`

---

### 3. Signal Update Handler (`src/handlers/update_handler.py:27-223`)

#### Entry Point: `handle_signal_update(event: NewMessage.Event)`

#### Parent Signal Lookup (lines 64-84)
**КРИТИЧНО:** Связывание ответа с родительским сигналом

```python
parent_msg_id = message.reply_to_msg_id  # Telethon API
if not parent_msg_id:
    logger.debug("Message is not a reply, ignoring")
    return

parent_signal = await db_find_signal_by_source_msg(
    source_chat_id=message.chat_id,
    source_message_id=parent_msg_id
)

if not parent_signal:
    logger.debug("Reply to unknown signal, ignoring", parent_msg_id=parent_msg_id)
    return

if not parent_signal.get('target_message_id'):
    logger.warning("Parent signal was not posted to target", signal_id=parent_signal['id'])
    return
```

**Логика:**
1. Получаем `reply_to_msg_id` из Telethon события
2. Ищем в БД сигнал с `source_message_id = reply_to_msg_id`
3. Если не найден → игнорируем (orphan reply)
4. Проверяем, что родитель был успешно опубликован (`target_message_id` не NULL)

#### NO USER FILTERING FOR UPDATES
**ВАЖНО:** В этом обработчике **нет проверки** `sender_id` вообще!

- Line 98: `source_user_id: message.sender_id` - просто записывается в БД
- **Нет фильтрации** по `config.allowed_users_list`
- **Нет проверки** что `sender_id` совпадает с `parent_signal['source_user_id']`

#### Database Flow
1. **Create update record** (lines 94-104):
   - Вставляет в `signal_updates`
   - Поля: `signal_id` (FK к родителю), `source_chat_id`, `source_message_id`, `source_user_id`
   - Статус: `PROCESSING`

2. **Media & translation** (lines 107-156)

3. **Post as reply** (lines 165-178):
   ```python
   posted_msg = await publisher.send_message(
       entity=config.TARGET_GROUP_ID,
       message=final_message,
       file=image_to_send,
       reply_to=parent_signal['target_message_id']  # Maintains threading
   )
   ```
   - **Ключ:** `reply_to=parent_signal['target_message_id']` - поддерживает цепочку ответов в target group

4. **Update DB** (lines 187-196):
   - `target_message_id`, `forward_message_id`
   - `status`: `POSTED`

---

## Data Flow: User ID Tracking

### In Database Schema (`migrations/001_init_schema.sql`)

#### Table: `signals` (lines 17-64)
```sql
source_user_id BIGINT NOT NULL,  -- Line 23: Author ID
```
- **NOT NULL constraint** - всегда записывается
- **No foreign key** - не ссылается на таблицу пользователей
- **No index** - нет индекса по `source_user_id`
- **Usage:** Только для аудита/логирования, не для бизнес-логики

#### Table: `signal_updates` (lines 79-117)
```sql
source_user_id BIGINT,  -- Line 88: nullable
```
- **Nullable** - может быть NULL
- **No foreign key, no index**
- **Usage:** Только для аудита

### In Application Code

#### Where `source_user_id` is SET:
1. **signal_handler.py:74**: `'source_user_id': message.sender_id or 0`
2. **update_handler.py:98**: `'source_user_id': message.sender_id`

#### Where `source_user_id` is READ:
**НИГДЕ** - поле записывается в БД, но **никогда не читается** для бизнес-логики

---

## Message Threading Mechanism

### How Replies are Linked

#### Source Group → Database
1. Telethon event: `message.reply_to_msg_id` содержит ID родительского сообщения
2. Query: `db_find_signal_by_source_msg(source_chat_id, source_message_id=reply_to_msg_id)`
3. Result: Получаем родительскую запись `signals` с полями:
   - `id` - internal DB ID
   - `target_message_id` - ID сообщения в target group
   - `forward_message_id` - ID сообщения в forward group (optional)

#### Database → Target Group
1. Получаем `parent_signal['target_message_id']`
2. Используем в `publisher.send_message(reply_to=target_message_id)`
3. Telegram автоматически создает reply chain в target group

### Threading Chain Example

```
SOURCE GROUP                   DATABASE                    TARGET GROUP
┌──────────────┐              ┌────────────┐             ┌──────────────┐
│ Msg 12345    │─────────────▶│ signals    │────────────▶│ Msg 67890    │
│ #Идея BTC    │  insert      │ id=1       │  reply_to   │ (translated) │
│ from user A  │              │ src_msg=12345│            │              │
└──────────────┘              │ tgt_msg=67890│            └──────────────┘
       │                      └────────────┘                     │
       │ reply_to=12345                                          │
       ▼                                                          ▼
┌──────────────┐              ┌────────────┐             ┌──────────────┐
│ Msg 12346    │─────────────▶│signal_updates│──────────▶│ Msg 67891    │
│ Update       │  insert      │ signal_id=1│  reply_to=  │ (translated) │
│ from user B  │              │ src_msg=12346│  67890     │              │
└──────────────┘              │ tgt_msg=67891│            └──────────────┘
                              └────────────┘
```

**ВАЖНО:** В цепочке **может отвечать любой пользователь** (user B ≠ user A), система не проверяет это.

---

## Configuration: User Filtering

### Config Source (`src/config.py:54-57, 289-310`)

```python
SOURCE_ALLOWED_USERS: Optional[str] = Field(
    default=None,
    description="Comma-separated list of allowed user IDs"
)
```

#### Helper Property (lines 289-310)
```python
@property
def allowed_users_list(self) -> List[int]:
    """Parse SOURCE_ALLOWED_USERS string to list of integers."""
    if not self.SOURCE_ALLOWED_USERS:
        return []  # Empty list = no filtering

    return [int(user_id.strip())
            for user_id in self.SOURCE_ALLOWED_USERS.split(",")
            if user_id.strip()]
```

**Behavior:**
- `None` or empty string → returns `[]` → **no filtering**
- `"123,456,789"` → returns `[123, 456, 789]`
- Invalid format → raises `ValueError`

#### Usage in Code
**ТОЛЬКО:** `signal_handler.py:59`:
```python
if config.allowed_users_list:  # Check if non-empty
    if sender_id not in config.allowed_users_list:
        return  # Ignore
```

---

## Gaps in Current Implementation

### 1. No "Active User Flow" Tracking
**Problem:** Нет концепции "активного пользователя потока"

- **New signal:** Проверяется `SOURCE_ALLOWED_USERS`, создается запись с `source_user_id`
- **Reply to signal:** Не проверяется `source_user_id` вообще
- **Result:** Любой пользователь может отвечать на сигнал любого другого пользователя

**Example:**
```
1. User A (allowed) posts signal #Идея → processed ✓
2. User B (not in allowed list) replies → processed ✓ (!)
3. User C (random) replies to B's reply → ignored (not a direct reply to signal)
```

### 2. No In-Memory State
**Problem:** Нет runtime состояния для отслеживания активных потоков

- **Database:** Все состояние в PostgreSQL
- **No caching:** Каждый reply делает SELECT запрос `db_find_signal_by_source_msg()`
- **No locking:** Нет механизма блокировки потока на конкретного пользователя

### 3. Reply Chain is NOT Fully User-Filtered
**Problem:** Система отслеживает threading по `reply_to_msg_id`, но не по `sender_id`

#### Current Logic:
```python
# update_handler.py:64-78
parent_msg_id = message.reply_to_msg_id
parent_signal = await db_find_signal_by_source_msg(
    source_chat_id=message.chat_id,
    source_message_id=parent_msg_id  # Only checks message ID
)
```

**Missing Check:**
```python
# Not implemented:
if parent_signal['source_user_id'] != message.sender_id:
    logger.debug("Reply from different user, ignoring")
    return
```

### 4. No Filtering for Nested Replies
**Problem:** Система обрабатывает только прямые ответы на сигналы (depth=1)

**Current behavior:**
- Signal (msg 1) → Update (msg 2, reply_to=1) → **processed** ✓
- Signal (msg 1) → Update (msg 2, reply_to=1) → Nested (msg 3, reply_to=2) → **ignored** (not a direct reply to signal)

**Reason:** `db_find_signal_by_source_msg()` ищет в таблице `signals`, но msg 2 находится в `signal_updates`

---

## Suggested Insertion Points for New Logic

### Option 1: In-Memory Flow State (Recommended)
**Location:** New module `src/state/flow_tracker.py`

**Structure:**
```python
class FlowTracker:
    """Tracks active message flows per user."""

    def __init__(self):
        self._active_flows = {}  # {signal_id: user_id}
        self._lock = asyncio.Lock()

    async def start_flow(self, signal_id: int, user_id: int):
        """Register new flow started by user."""
        async with self._lock:
            self._active_flows[signal_id] = user_id

    async def is_allowed(self, signal_id: int, user_id: int) -> bool:
        """Check if user is allowed to continue this flow."""
        async with self._lock:
            return self._active_flows.get(signal_id) == user_id

    async def end_flow(self, signal_id: int):
        """Clear flow (optional, for cleanup)."""
        async with self._lock:
            self._active_flows.pop(signal_id, None)
```

**Integration:**
1. **signal_handler.py:80** (after DB insert):
   ```python
   signal_id = await db_insert_signal(signal_data)
   await flow_tracker.start_flow(signal_id, message.sender_id)
   ```

2. **update_handler.py:79** (after finding parent):
   ```python
   parent_signal = await db_find_signal_by_source_msg(...)
   if not await flow_tracker.is_allowed(parent_signal['id'], message.sender_id):
       logger.debug("Reply from different user, ignoring flow")
       return
   ```

### Option 2: Database-Based Flow State
**Location:** Modify `signals` table schema

**Migration:**
```sql
ALTER TABLE signals
ADD COLUMN active_flow_user_id BIGINT,
ADD COLUMN flow_started_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX idx_signals_active_flow ON signals(active_flow_user_id)
WHERE active_flow_user_id IS NOT NULL;
```

**Integration:**
1. **signal_handler.py:87** (update query):
   ```python
   await db_update_signal(signal_id, {
       'status': 'PROCESSING',
       'active_flow_user_id': message.sender_id,
       'flow_started_at': datetime.utcnow()
   })
   ```

2. **update_handler.py** (add check):
   ```python
   parent_signal = await db_find_signal_by_source_msg(...)
   if parent_signal['active_flow_user_id'] != message.sender_id:
       logger.debug("Reply from different user in active flow")
       return
   ```

### Option 3: Enhanced User Filtering in update_handler
**Location:** `src/handlers/update_handler.py:79` (after line)

**Simple addition:**
```python
# After finding parent_signal
if config.allowed_users_list:  # If filtering enabled
    if parent_signal['source_user_id'] != message.sender_id:
        logger.debug("Update from different user, ignoring",
                    parent_user=parent_signal['source_user_id'],
                    current_user=message.sender_id)
        return
```

**Pros:** Minimal change, no new state
**Cons:** Не блокирует поток, просто игнорирует других пользователей по факту

---

## Key Patterns Identified

### 1. Event-Driven Architecture
- **Telethon event loop** → `@reader_client.on(events.NewMessage)`
- **Async task spawning** via `create_tracked_task()` (main.py:54-59)
- **Background task tracking** for graceful shutdown

### 2. Database as Single Source of Truth
- **No in-memory caching** кроме config
- **Idempotency checks** через `db_find_signal_by_source_msg()` / `db_find_update_by_source_msg()`
- **Transactional safety** через asyncpg connection pool

### 3. Pipeline Processing Pattern
Both handlers follow:
1. Idempotency check
2. User filtering (only new signals)
3. Create DB record with status PENDING
4. Update to PROCESSING
5. Parallel tasks (translation, OCR, forwarding)
6. Post to Telegram
7. Update DB with status POSTED/ERROR
8. Cleanup media

### 4. Reply Chain Tracking via Database
- Source `reply_to_msg_id` → DB lookup → Target `reply_to` parameter
- **No circular references** - только forward links (child → parent)

---

## Metadata

```yaml
---
status: SUCCESS
files_analyzed: 6
symbols_traced: 8
data_flows_documented: 3
patterns_identified: [Event-Driven, Database-as-Truth, Pipeline, Reply-Chain-Tracking]
confidence: high
---
```
