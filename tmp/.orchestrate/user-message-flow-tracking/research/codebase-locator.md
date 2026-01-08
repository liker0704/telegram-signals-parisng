# File Locations: User Message Flow Tracking

## Summary

Telegram-бот обрабатывает входящие сообщения из source-группы и пересылает их в target-группу. Текущая система поддерживает базовую фильтрацию по списку разрешенных пользователей (`SOURCE_ALLOWED_USERS`), но не отслеживает состояние потока сообщений от конкретного пользователя.

---

## Implementation Files

### Message Processing Entry Point
- `/home/liker/projects/telegram-signals-parisng/src/main.py` - Основной файл с регистрацией обработчиков событий
  - Строка 78: `@reader_client.on(events.NewMessage(...))` - регистрация обработчика
  - Строка 79-108: `async def on_new_message(event)` - роутинг входящих сообщений
  - Логика роутинга: сообщения с `#Идея` → `handle_new_signal`, ответы → `handle_signal_update`

### Core Message Handlers
- `/home/liker/projects/telegram-signals-parisng/src/handlers/signal_handler.py` - Обработка новых сигналов
  - Строка 23: `async def handle_new_signal(event: NewMessage.Event)`
  - Строка 59-64: Проверка `allowed_users_list` - фильтрация по sender_id
  - Строка 60: `sender_id = message.sender_id` - получение ID отправителя
  - Строка 41: `message = event.message` - доступ к объекту сообщения

- `/home/liker/projects/telegram-signals-parisng/src/handlers/update_handler.py` - Обработка ответов на сигналы
  - Строка 27: `async def handle_signal_update(event: NewMessage.Event)`
  - Строка 47: `message = event.message` - доступ к объекту сообщения
  - Строка 64: `parent_msg_id = message.reply_to_msg_id` - определение родительского сообщения
  - Строка 98: `source_user_id: message.sender_id` - сохранение ID отправителя в БД

- `/home/liker/projects/telegram-signals-parisng/src/handlers/forward_helper.py` - Пересылка оригинальных сообщений в третью группу
  - Содержит функцию `forward_to_third_group_if_enabled`
  - Строка 45-52: Использует `asyncio.wait_for` с таймаутом

### User Identification
- `/home/liker/projects/telegram-signals-parisng/src/config.py` - Конфигурация фильтрации пользователей
  - Строка 54: `SOURCE_ALLOWED_USERS: Optional[str]` - ENV переменная со списком разрешенных user_id
  - Строка 289-309: `def allowed_users_list() -> List[int]` - парсинг списка пользователей из строки

---

## Database Layer

### State Storage
- `/home/liker/projects/telegram-signals-parisng/src/db/queries.py` - SQL-запросы для работы с сигналами и обновлениями
  - Строка 33: `async def db_insert_signal(signal_data: dict)` - создание записи сигнала
  - Строка 120: `async def db_find_signal_by_source_msg()` - поиск сигнала по source message
  - Строка 138: `async def db_find_signal_by_id(signal_id: int)` - поиск сигнала по ID
  - Строка 149: `async def db_insert_signal_update(update_data: dict)` - создание записи обновления
  - Строка 41: Упоминание `source_user_id` как обязательного поля
  - Строка 52-66: INSERT запрос для сигналов с полем `source_user_id`
  - Строка 158-178: INSERT запрос для updates с полем `source_user_id`

- `/home/liker/projects/telegram-signals-parisng/src/db/connection.py` - Управление подключением к PostgreSQL

### Database Schema
- `/home/liker/projects/telegram-signals-parisng/migrations/001_init_schema.sql` - Схема базы данных
  - Строка 17: `CREATE TABLE signals` - таблица сигналов
  - Строка 79: `CREATE TABLE signal_updates` - таблица обновлений сигналов
  - Обе таблицы содержат поля: `source_chat_id`, `source_message_id`, `source_user_id`
  - Строка 83: `signal_id INTEGER ... REFERENCES signals(id)` - связь updates с parent signal

- `/home/liker/projects/telegram-signals-parisng/migrations/002_add_forward_columns.sql` - Добавление полей для форвардинга
  - Добавляет `forward_message_id` и `forward_group_id` в обе таблицы

---

## Media Processing

### Media Handling
- `/home/liker/projects/telegram-signals-parisng/src/media/downloader.py` - Скачивание и обработка медиа из сообщений
- `/home/liker/projects/telegram-signals-parisng/src/media/__init__.py` - Экспорт функции `download_and_process_media`

---

## Test Files

### Unit Tests
- `/home/liker/projects/telegram-signals-parisng/tests/test_forward_helper.py` - Тесты для форвардинга
- `/home/liker/projects/telegram-signals-parisng/tests/test_parser.py` - Тесты парсера сигналов
- `/home/liker/projects/telegram-signals-parisng/tests/test_formatters.py` - Тесты форматирования сообщений

### Test Scripts
- `/home/liker/projects/telegram-signals-parisng/scripts/check_group_messages.py` - Проверка сообщений группы
- `/home/liker/projects/telegram-signals-parisng/scripts/test_last_signals.py` - Тестирование последних сигналов
- `/home/liker/projects/telegram-signals-parisng/scripts/get_user_id.py` - Получение user_id
- `/home/liker/projects/telegram-signals-parisng/scripts/check_users.py` - Проверка пользователей

---

## Configuration Files

### Environment
- `/home/liker/projects/telegram-signals-parisng/.env.example` - Пример конфигурации
  - Содержит `SOURCE_ALLOWED_USERS` для фильтрации
  - Содержит `SOURCE_GROUP_ID`, `TARGET_GROUP_ID`, `THIRD_GROUP_ID`

### Setup
- `/home/liker/projects/telegram-signals-parisng/src/telethon_setup.py` - Инициализация Telethon клиентов

---

## Related Directories

### Handlers Directory (`src/handlers/`)
Содержит 4 файла:
- `__init__.py` - Инициализация модуля
- `signal_handler.py` - Обработчик новых сигналов
- `update_handler.py` - Обработчик обновлений/ответов
- `forward_helper.py` - Пересылка в третью группу

### Database Directory (`src/db/`)
Содержит 3 файла:
- `__init__.py` - Инициализация модуля
- `queries.py` - SQL-запросы
- `connection.py` - Управление подключением

### Migrations Directory (`migrations/`)
Содержит 2 SQL файла:
- `001_init_schema.sql` - Базовая схема БД
- `002_add_forward_columns.sql` - Добавление полей форвардинга

---

## Key Data Structures

### Message Event Object (Telethon)
- `event.message` - объект сообщения
- `event.message.sender_id` - ID отправителя (используется для идентификации пользователя)
- `event.message.chat_id` - ID чата
- `event.message.id` - ID сообщения
- `event.message.is_reply` - флаг ответа
- `event.message.reply_to_msg_id` - ID родительского сообщения
- `event.message.text` - текст сообщения
- `event.message.date` - дата сообщения

### Database Records
Поля `signals` и `signal_updates`:
- `source_chat_id` - ID исходного чата
- `source_message_id` - ID исходного сообщения
- `source_user_id` - ID пользователя-отправителя
- `target_message_id` - ID сообщения в целевой группе
- `status` - статус обработки (PENDING, PROCESSING, POSTED, ERROR_*)

---

## Entry Points for Message Flow

### Main Entry Point
1. **`src/main.py:78-108`** - Регистрация обработчика `@reader_client.on(events.NewMessage(...))`
   - Фильтр: `chats=[config.SOURCE_GROUP_ID]`
   - Фильтр: `incoming=True, outgoing=True`

### Routing Logic
2. **`src/main.py:97-103`** - Роутинг по типу сообщения:
   - `if is_signal(text)` → `handle_new_signal(event)`
   - `elif message.is_reply` → `handle_signal_update(event)`
   - `else` → игнорируется

### Processing Handlers
3. **`src/handlers/signal_handler.py:23`** - Обработка новых сигналов
4. **`src/handlers/update_handler.py:27`** - Обработка ответов

---

## Current Filtering Mechanism

### Where Filtering Happens
- **Location**: `src/handlers/signal_handler.py:59-64`
- **Mechanism**: Проверка `sender_id` против статического списка `config.allowed_users_list`
- **Scope**: Применяется только к новым сигналам (`handle_new_signal`), НЕ к обновлениям (`handle_signal_update`)

### Configuration
- **ENV Variable**: `SOURCE_ALLOWED_USERS` (comma-separated user IDs)
- **Parser**: `src/config.py:289` - метод `allowed_users_list()`
- **Format**: `"123456789,987654321"` → `[123456789, 987654321]`

---

## State Management Notes

### Current State Storage
- **Persistent State**: PostgreSQL база данных через `src/db/queries.py`
- **In-Memory State**: НЕТ - все состояние хранится в БД
- **Session/Flow Tracking**: НЕТ - нет отслеживания активного потока от пользователя

### No Caching/Redis
Поиск показал отсутствие Redis или in-memory кэширования для состояния потока сообщений.

---

## Naming Patterns Observed

### File Naming
- Handlers: `*_handler.py` (signal_handler, update_handler)
- Helpers: `*_helper.py` (forward_helper)
- Queries: `queries.py` для SQL-операций
- Setup: `*_setup.py` для инициализации

### Function Naming
- Handlers: `handle_*` (handle_new_signal, handle_signal_update)
- Database ops: `db_*` (db_insert_signal, db_find_signal_by_source_msg)
- Async functions: все обработчики используют `async def`

### Variable Naming
- User ID: `sender_id` (от Telethon), `source_user_id` (в БД)
- Message ID: `message.id` (текущее), `source_message_id` (в БД)
- Chat ID: `chat_id` (от Telethon), `source_chat_id` (в БД)

---

## Documentation Files
- `/home/liker/projects/telegram-signals-parisng/docs/architecture.md` - Описание архитектуры
- `/home/liker/projects/telegram-signals-parisng/docs/api.md` - API документация
- `/home/liker/projects/telegram-signals-parisng/docs/testing.md` - Тестирование
- `/home/liker/projects/telegram-signals-parisng/DevTS_Telegram_Bot.md` - Общая документация бота

---

```yaml
---
status: SUCCESS
files_found: 35
categories:
  implementation: 12
  tests: 7
  config: 6
  docs: 8
  types: 2
confidence: high
---
```
