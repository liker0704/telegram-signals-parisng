# Tasks for: user-message-flow-tracking

Generated: 2026-01-08 12:30:00
Total tasks: 6

## Summary

| Phase | Tasks | Parallel Possible |
|-------|-------|-------------------|
| Phase 1 | 2 | 0 |
| Phase 2 | 1 | 0 |
| Phase 3 | 1 | 0 |
| Phase 4 | 2 | 2 |

## Task List

### task-01: create-state-package

- **Phase**: 1
- **Type**: implement
- **Risk**: low
- **Review**: false
- **Description**: Создать пакет `src/state/` с `__init__.py`
- **Files**:
  - `src/state/__init__.py` (create)
- **Details**:
  - Создать директорию `src/state/`
  - Создать `__init__.py` с docstring
  - Экспортировать основные функции
- **Depends on**: none
- **Blocks**: task-02
- **Agent**: implementer
- **Verification**:
  - `python -c "import src.state"`
- **Status**: pending

---

### task-02: implement-flow-tracker

- **Phase**: 1
- **Type**: implement
- **Risk**: low
- **Review**: true
- **Description**: Реализовать `flow_tracker.py` с TTL-based tracking
- **Files**:
  - `src/state/flow_tracker.py` (create)
- **Details**:
  - Глобальный `_active_flows: Dict[int, FlowInfo]`
  - `FlowInfo` dataclass с `user_id`, `timestamp`
  - `FLOW_TTL = 259200` (72 часа, configurable через env)
  - `start_flow(signal_id: int, user_id: int) -> None`
  - `get_flow_owner(signal_id: int) -> Optional[int]`
  - `is_allowed(signal_id: int, user_id: int) -> bool`
  - `end_flow(signal_id: int) -> None`
  - `cleanup_expired() -> int` (returns count cleaned)
  - Periodic cleanup каждые 100 операций
  - Max flows limit (10000) с force cleanup
  - Logging для debug
- **Depends on**: task-01
- **Blocks**: task-03, task-04
- **Agent**: implementer
- **Verification**:
  - `python -c "from src.state.flow_tracker import start_flow, is_allowed; start_flow(1, 100); assert is_allowed(1, 100); assert not is_allowed(1, 200)"`
- **Status**: pending

---

### task-03: integrate-signal-handler

- **Phase**: 2
- **Type**: modify
- **Risk**: low
- **Review**: false
- **Description**: Добавить `start_flow()` в signal_handler.py
- **Files**:
  - `src/handlers/signal_handler.py` (modify)
- **Details**:
  - Import `from src.state.flow_tracker import start_flow`
  - После `signal_id = await db_insert_signal(signal_data)` (примерно line 80)
  - Добавить: `start_flow(signal_id, message.sender_id)`
  - Добавить log: `logger.debug("Started flow tracking", signal_id=signal_id, user_id=message.sender_id)`
- **Depends on**: task-02
- **Blocks**: task-04
- **Agent**: implementer
- **Verification**:
  - `pytest tests/test_signal_handler.py -v` (если существует)
  - `python -c "from src.handlers.signal_handler import handle_new_signal"`
- **Status**: pending

---

### task-04: integrate-update-handler

- **Phase**: 3
- **Type**: modify
- **Risk**: medium
- **Review**: true
- **Description**: Добавить проверку is_allowed() с DB fallback в update_handler.py
- **Files**:
  - `src/handlers/update_handler.py` (modify)
- **Details**:
  - Import `from src.state.flow_tracker import is_allowed, start_flow, get_flow_owner`
  - После проверки `if not parent_signal.get('target_message_id')` (line ~84)
  - Добавить блок проверки:
    ```python
    # Check if sender is allowed in this flow
    signal_id = parent_signal['id']
    signal_author = parent_signal.get('source_user_id')

    # First check in-memory cache
    cached_owner = get_flow_owner(signal_id)

    if cached_owner is not None:
        # Cache hit - use cached value
        if cached_owner != message.sender_id:
            logger.debug("Reply from different user (cached), ignoring",
                        signal_id=signal_id,
                        sender_id=message.sender_id,
                        flow_owner=cached_owner)
            return
    elif signal_author and signal_author > 0 and signal_author != message.sender_id:
        # Cache miss - check DB and reject if mismatch
        logger.debug("Reply from different user (DB), ignoring",
                    signal_id=signal_id,
                    sender_id=message.sender_id,
                    signal_author=signal_author)
        return
    else:
        # Cache miss but allowed - populate cache for future
        # Skip if source_user_id is 0 (anonymous/unknown sender)
        if signal_author and signal_author > 0:
            start_flow(signal_id, signal_author)
    ```
- **Depends on**: task-02, task-03
- **Blocks**: task-05, task-06
- **Agent**: implementer
- **Verification**:
  - `pytest tests/test_update_handler.py -v` (если существует)
  - Manual: проверить что ответы от других пользователей игнорируются
- **Status**: pending

---

### task-05: create-flow-tracker-tests

- **Phase**: 4
- **Type**: test
- **Risk**: low
- **Review**: false
- **Description**: Создать unit tests для flow_tracker.py
- **Files**:
  - `tests/test_flow_tracker.py` (create)
- **Details**:
  - Test `start_flow()` регистрирует flow
  - Test `is_allowed()` returns True для owner
  - Test `is_allowed()` returns False для другого user
  - Test `is_allowed()` returns True после TTL expiration (mock time)
  - Test `get_flow_owner()` returns correct owner
  - Test `end_flow()` removes flow
  - Test `cleanup_expired()` removes expired entries
  - Test max flows limit с force cleanup
  - Use `pytest` fixtures и `unittest.mock` для time
- **Depends on**: task-04
- **Blocks**: none
- **Agent**: tester
- **Verification**:
  - `pytest tests/test_flow_tracker.py -v`
- **Status**: pending

---

### task-06: update-handler-tests

- **Phase**: 4
- **Type**: test
- **Risk**: low
- **Review**: false
- **Description**: Добавить тесты для user filtering в update_handler
- **Files**:
  - `tests/test_update_handler.py` (create or modify)
- **Details**:
  - Test: reply from same user as signal author → allowed
  - Test: reply from different user → ignored (returns early)
  - Test: reply when cache miss → checks DB, populates cache
  - Test: reply to signal with source_user_id=0 → allowed (anonymous sender)
  - Test: reply to old signal without source_user_id → allowed (fallback)
  - Mock database queries и flow_tracker functions
- **Depends on**: task-04
- **Blocks**: none
- **Agent**: tester
- **Verification**:
  - `pytest tests/test_update_handler.py -v`
- **Status**: pending

---

## Dependency Graph

```
Phase 1:
  task-01 ──→ task-02

Phase 2:
  task-02 ──→ task-03

Phase 3:
  task-03 ──→ task-04

Phase 4:
  task-04 ──┬──→ task-05 [parallel]
            └──→ task-06 [parallel]
```

## Execution Batches

### Batch 1 (start)
- task-01: create-state-package

### Batch 2 (after batch 1)
- task-02: implement-flow-tracker

### Batch 3 (after batch 2)
- task-03: integrate-signal-handler

### Batch 4 (after batch 3)
- task-04: integrate-update-handler

### Batch 5 (after batch 4) - PARALLEL
- task-05: create-flow-tracker-tests [parallel]
- task-06: update-handler-tests [parallel]

## Verification Checklist

After all tasks complete:
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Type check passes: `mypy src/` (если настроен)
- [ ] Lint passes: `ruff check src/` (если настроен)
- [ ] Import check: `python -c "from src.state.flow_tracker import start_flow, is_allowed"`
- [ ] Manual verification:
  - [ ] Создать сигнал от User A
  - [ ] Ответить от User A → проходит
  - [ ] Ответить от User B → игнорируется
  - [ ] Проверить logs на debug сообщения
