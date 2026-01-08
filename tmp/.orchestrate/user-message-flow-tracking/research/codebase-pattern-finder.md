# Codebase Pattern Examples: User Message Flow Tracking

## Pattern Examples for Implementation

### Pattern 1: Global State Management with Module-Level Variables

**Found in**: `/home/liker/projects/telegram-signals-parisng/src/telethon_setup.py:14-16`

**Used for**: Managing singleton Telegram client instances

```python
# Global client instances
_reader_client: Optional[TelegramClient] = None
_publisher_client: Optional[TelegramClient] = None
```

**Found in**: `/home/liker/projects/telegram-signals-parisng/src/db/connection.py:13-15`

**Used for**: Database connection pool singleton

```python
# Global connection pool
_pool: Optional[asyncpg.Pool] = None
_init_lock: Optional[asyncio.Lock] = None
```

**Found in**: `/home/liker/projects/telegram-signals-parisng/src/main.py:36-38`

**Used for**: Tracking running tasks and shutdown state

```python
# Global state for graceful shutdown
_shutdown_event: asyncio.Event = None
_running_tasks: Set[asyncio.Task] = set()
```

**Key aspects**:
- Module-level variables with `_` prefix (private convention)
- `Optional[]` typing for None initialization
- Getter functions to access the state
- Initialization with lazy loading or explicit init functions

### Pattern 2: User ID Validation in Handlers

**Found in**: `/home/liker/projects/telegram-signals-parisng/src/handlers/signal_handler.py:58-64`

**Used for**: Filtering signals from allowed users only

```python
try:
    # Check if sender is allowed (if configured)
    if config.allowed_users_list:
        sender_id = message.sender_id
        if sender_id not in config.allowed_users_list:
            logger.debug("Signal from unauthorized user, ignoring",
                        sender_id=sender_id)
            return
```

**Key aspects**:
- Early return pattern for validation failures
- Check if config is set before validation (`if config.allowed_users_list`)
- Use `sender_id` from Telethon message object
- Log rejection for debugging (debug level, not info)
- Silent rejection (no error, just return)

**Related configuration**: `/home/liker/projects/telegram-signals-parisng/src/config.py:54-57`

```python
SOURCE_ALLOWED_USERS: Optional[str] = Field(
    default=None,
    description="Comma-separated list of allowed user IDs"
)
```

**Helper property**: `/home/liker/projects/telegram-signals-parisng/src/config.py:289-310`

```python
@property
def allowed_users_list(self) -> List[int]:
    """
    Parse SOURCE_ALLOWED_USERS string to list of integers.

    Returns:
        List of user IDs, or empty list if SOURCE_ALLOWED_USERS is None/empty.
    """
    if not self.SOURCE_ALLOWED_USERS:
        return []

    try:
        # Split by comma and convert to integers, filtering out empty strings
        return [
            int(user_id.strip())
            for user_id in self.SOURCE_ALLOWED_USERS.split(",")
            if user_id.strip()
        ]
    except ValueError as e:
        raise ValueError(
            f"Invalid SOURCE_ALLOWED_USERS format. "
            f"Expected comma-separated integers, got: {self.SOURCE_ALLOWED_USERS}"
        ) from e
```

### Pattern 3: Parent Signal Lookup with Validation

**Found in**: `/home/liker/projects/telegram-signals-parisng/src/handlers/update_handler.py:63-84`

**Used for**: Finding parent signal when processing replies

```python
# Step 1: Find parent signal
parent_msg_id = message.reply_to_msg_id
if not parent_msg_id:
    logger.debug("Message is not a reply, ignoring")
    return

parent_signal = await db_find_signal_by_source_msg(
    source_chat_id=message.chat_id,
    source_message_id=parent_msg_id
)

# Step 2: Check if parent exists
if not parent_signal:
    logger.debug("Reply to unknown signal, ignoring",
                parent_msg_id=parent_msg_id)
    return

# Check if parent was successfully posted
if not parent_signal.get('target_message_id'):
    logger.warning("Parent signal was not posted to target",
                  signal_id=parent_signal['id'])
    return
```

**Database query**: `/home/liker/projects/telegram-signals-parisng/src/db/queries.py:120-135`

```python
async def db_find_signal_by_source_msg(
    source_chat_id: int,
    source_message_id: int
) -> Optional[dict]:
    """
    Find a signal by source chat and message ID.

    Returns:
        dict or None: The signal record as dict, or None if not found
    """
    query = """
        SELECT * FROM signals
        WHERE source_chat_id = $1 AND source_message_id = $2
    """
    row = await fetchrow(query, source_chat_id, source_message_id)
    return dict(row) if row else None
```

**Key aspects**:
- Multiple validation steps with early returns
- Database lookup for parent record
- Check parent exists and is in valid state
- Access parent fields with `.get()` for safety
- Different log levels: debug for expected cases, warning for unexpected
- Returns dict or None (not raising exceptions)

### Pattern 4: Idempotency Check Pattern

**Found in**: `/home/liker/projects/telegram-signals-parisng/src/handlers/signal_handler.py:42-51`

**Used for**: Preventing duplicate processing of same message

```python
# Idempotency check - skip if already processed
existing_signal = await db_find_signal_by_source_msg(
    source_chat_id=message.chat_id,
    source_message_id=message.id
)
if existing_signal:
    logger.info("Signal already processed, skipping",
               source_msg_id=message.id,
               existing_signal_id=existing_signal.get('id'))
    return
```

**Found in**: `/home/liker/projects/telegram-signals-parisng/src/handlers/update_handler.py:48-56`

**Used for**: Same pattern for updates

```python
# Idempotency check - skip if already processed
existing_update = await db_find_update_by_source_msg(
    source_chat_id=message.chat_id,
    source_message_id=message.id
)
if existing_update:
    logger.info("Signal update already processed, skipping",
               source_msg_id=message.id)
    return
```

**Key aspects**:
- Database lookup at start of handler
- Early return if record exists
- Log at info level (not error or warning)
- Use source_chat_id + source_message_id as composite key

### Pattern 5: Frozenset for Validation Whitelists

**Found in**: `/home/liker/projects/telegram-signals-parisng/src/db/queries.py:12-26`

**Used for**: Validating allowed columns for updates

```python
# Whitelist of allowed columns for UPDATE operations
ALLOWED_SIGNAL_COLUMNS = frozenset({
    'status', 'pair', 'direction', 'timeframe', 'entry_range',
    'tp1', 'tp2', 'tp3', 'sl', 'risk_percent', 'target_chat_id',
    'target_message_id', 'translated_text', 'image_ocr_text',
    'processed_at', 'error_message', 'image_local_path',
    'forward_chat_id', 'forward_message_id'
})

ALLOWED_SIGNAL_UPDATE_COLUMNS = frozenset({
    'status', 'pair', 'direction', 'timeframe', 'entry_range',
    'tp1', 'tp2', 'tp3', 'sl', 'risk_percent', 'target_chat_id',
    'target_message_id', 'translated_text', 'image_ocr_text',
    'processed_at', 'error_message', 'image_local_path',
    'forward_chat_id', 'forward_message_id'
})
```

**Usage in validation**: `/home/liker/projects/telegram-signals-parisng/src/db/queries.py:98-100`

```python
# Validate column names against whitelist
invalid_keys = set(data.keys()) - ALLOWED_SIGNAL_COLUMNS
if invalid_keys:
    raise ValueError(f"Invalid column names: {invalid_keys}")
```

**Found in**: `/home/liker/projects/telegram-signals-parisng/src/utils/security.py:12-13`

```python
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG', 'GIF', 'WEBP', 'BMP'}
```

**Key aspects**:
- Module-level constants with UPPERCASE naming
- `frozenset` for immutable validation sets
- Set operations for validation (`set(keys) - ALLOWED`)
- Raise ValueError for invalid input

### Pattern 6: Tracked Task Management

**Found in**: `/home/liker/projects/telegram-signals-parisng/src/main.py:38-59`

**Used for**: Managing async tasks with automatic cleanup

```python
# Global state for graceful shutdown
_running_tasks: Set[asyncio.Task] = set()


def _task_done_callback(task: asyncio.Task) -> None:
    """Remove completed task from tracking set and log errors."""
    _running_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("Background task failed",
                    task_name=task.get_name(),
                    error=str(exc),
                    exc_info=exc)


def create_tracked_task(coro, name: str = None) -> asyncio.Task:
    """Create an asyncio task that is tracked for graceful shutdown."""
    task = asyncio.create_task(coro, name=name)
    _running_tasks.add(task)
    task.add_done_callback(_task_done_callback)
    return task
```

**Usage**: `/home/liker/projects/telegram-signals-parisng/src/main.py:99-102`

```python
if is_signal(text):
    # New signal with #Идея marker
    create_tracked_task(handle_new_signal(event), name=f"signal_{message.id}")
elif message.is_reply:
    # Reply to some message - handler will check if parent is a signal
    create_tracked_task(handle_signal_update(event), name=f"update_{message.id}")
```

**Key aspects**:
- Global Set to track tasks
- Done callback for automatic cleanup
- Error logging in callback
- Named tasks for debugging
- Use message.id in task name for traceability

### Pattern 7: Config-Based Feature Toggle

**Found in**: `/home/liker/projects/telegram-signals-parisng/src/handlers/forward_helper.py:13-15`

**Used for**: Checking if optional feature is enabled

```python
def is_forwarding_enabled() -> bool:
    """Check if forwarding is enabled in configuration."""
    return config.FORWARD_GROUP_ID is not None
```

**Usage in handler**: `/home/liker/projects/telegram-signals-parisng/src/handlers/signal_handler.py:121-127`

```python
# Forward original message task (parallel with translation)
forward_task = (
    forward_original_message(
        original_text=message.text or '',
        media_path=media_info['local_path'] if media_info else None,
        reply_to_forward_id=None  # New signal, no parent
    )
    if is_forwarding_enabled() else asyncio.sleep(0)
)
```

**Key aspects**:
- Simple helper function for readability
- Check config value is not None
- Conditional task execution (actual work vs no-op)
- Use `asyncio.sleep(0)` as no-op placeholder in gather

### Pattern 8: Database State Tracking (Existing)

**Schema**: Database already tracks `source_user_id` in signals table

**Insert pattern**: `/home/liker/projects/telegram-signals-parisng/src/handlers/signal_handler.py:71-79`

```python
# Step 1: Create initial DB record
signal_data = {
    'source_chat_id': message.chat_id,
    'source_message_id': message.id,
    'source_user_id': message.sender_id or 0,
    'original_text': message.text or '',
    'status': 'PENDING',
    'created_at': message.date or datetime.utcnow()
}
signal_id = await db_insert_signal(signal_data)
```

**Update insert**: `/home/liker/projects/telegram-signals-parisng/src/handlers/update_handler.py:94-103`

```python
# Step 3: Create update record
update_data = {
    'signal_id': parent_signal['id'],
    'source_chat_id': message.chat_id,
    'source_message_id': message.id,
    'source_user_id': message.sender_id,
    'original_text': message.text or '',
    'status': 'PROCESSING',
    'created_at': message.date or datetime.utcnow()
}
update_id = await db_insert_signal_update(update_data)
```

**Key aspects**:
- Database already stores sender information
- Use `message.sender_id` directly from Telethon
- Fallback to 0 for signals (defensive)
- No fallback for updates (nullable)

## Testing Patterns

**Found in**: `/home/liker/projects/telegram-signals-parisng/tests/test_forward_helper.py:10-23`

**Used for**: Testing configuration-based behavior

```python
class TestIsForwardingEnabled:
    """Tests for is_forwarding_enabled function."""

    def test_returns_true_when_configured(self):
        """Should return True when FORWARD_GROUP_ID is set."""
        with patch('src.handlers.forward_helper.config') as mock_config:
            mock_config.FORWARD_GROUP_ID = -100123456789
            assert is_forwarding_enabled() is True

    def test_returns_false_when_not_configured(self):
        """Should return False when FORWARD_GROUP_ID is None."""
        with patch('src.handlers.forward_helper.config') as mock_config:
            mock_config.FORWARD_GROUP_ID = None
            assert is_forwarding_enabled() is False
```

**Key aspects**:
- Use `unittest.mock.patch` for config mocking
- Test both enabled and disabled states
- Clear docstrings describing expected behavior
- Simple assertions

## Pattern Usage in Codebase

### Global State Management
- Database pool: `/home/liker/projects/telegram-signals-parisng/src/db/connection.py:14`
- Telegram clients: `/home/liker/projects/telegram-signals-parisng/src/telethon_setup.py:14-16`
- Running tasks: `/home/liker/projects/telegram-signals-parisng/src/main.py:38`
- Translation semaphore: `/home/liker/projects/telegram-signals-parisng/src/translators/fallback.py:16`

### User/Sender Validation
- Signal handler only: `/home/liker/projects/telegram-signals-parisng/src/handlers/signal_handler.py:58-64`
- Update handler: No sender validation currently

### Parent Lookup Patterns
- Update handler: `/home/liker/projects/telegram-signals-parisng/src/handlers/update_handler.py:63-84`

### Configuration Helpers
- Parse comma-separated IDs: `/home/liker/projects/telegram-signals-parisng/src/config.py:289-310`
- Feature toggle functions: `/home/liker/projects/telegram-signals-parisng/src/handlers/forward_helper.py:13-15`

## Related Utilities

### Database Queries
- `db_find_signal_by_source_msg()`: `/home/liker/projects/telegram-signals-parisng/src/db/queries.py:120`
- `db_find_update_by_source_msg()`: `/home/liker/projects/telegram-signals-parisng/src/db/queries.py:216`
- `db_insert_signal()`: `/home/liker/projects/telegram-signals-parisng/src/db/queries.py:33`
- `db_update_signal()`: `/home/liker/projects/telegram-signals-parisng/src/db/queries.py:86`

### Message Properties
- `message.sender_id`: User ID from Telethon
- `message.reply_to_msg_id`: Parent message ID for replies
- `message.is_reply`: Boolean check if message is a reply
- `message.chat_id`: Group/chat ID
- `message.id`: Message ID

### Logging Patterns
- Early return validation: `logger.debug()` for expected rejections
- Errors: `logger.error()` with `exc_info=True`
- Info: `logger.info()` for normal flow events
- Warning: `logger.warning()` for unexpected but non-fatal cases

---

## Implementation Recommendations Based on Existing Patterns

### Option 1: In-Memory State Tracker (Follows Global State Pattern)

Create `/home/liker/projects/telegram-signals-parisng/src/state/flow_tracker.py`:

```python
# Following pattern from src/telethon_setup.py and src/db/connection.py
from typing import Optional, Dict

# Global state: signal_id -> user_id mapping
_active_flows: Dict[int, int] = {}


def start_flow(signal_id: int, user_id: int) -> None:
    """Mark signal as having active flow from specific user."""
    _active_flows[signal_id] = user_id


def get_flow_user(signal_id: int) -> Optional[int]:
    """Get user ID for active flow, or None."""
    return _active_flows.get(signal_id)


def end_flow(signal_id: int) -> None:
    """Remove flow tracking for signal."""
    _active_flows.pop(signal_id, None)


def is_user_allowed_in_flow(signal_id: int, user_id: int) -> bool:
    """Check if user is allowed to update this signal."""
    flow_user = _active_flows.get(signal_id)
    if flow_user is None:
        return True  # No flow started yet
    return flow_user == user_id
```

**Usage in update_handler.py**:

```python
# After finding parent_signal
from src.state.flow_tracker import is_user_allowed_in_flow, start_flow

# Check if sender matches flow
if not is_user_allowed_in_flow(parent_signal['id'], message.sender_id):
    logger.debug("Update from different user, ignoring",
                signal_id=parent_signal['id'],
                sender_id=message.sender_id,
                expected_user=get_flow_user(parent_signal['id']))
    return

# Start flow on first update
start_flow(parent_signal['id'], message.sender_id)
```

### Option 2: Database Column Approach (Simpler, No New Module)

Add validation in update_handler using existing DB pattern:

```python
# After finding parent_signal (line 72)
parent_signal = await db_find_signal_by_source_msg(...)

# Check if this is first update or matches original user
original_user_id = parent_signal.get('source_user_id')
if original_user_id and message.sender_id != original_user_id:
    logger.debug("Update from different user than signal author, ignoring",
                signal_id=parent_signal['id'],
                sender_id=message.sender_id,
                original_user=original_user_id)
    return
```

### Option 3: Hybrid - Simple Parent Check (Minimal Change)

Just compare with parent's source_user_id (already in DB):

```python
# In update_handler.py after line 78
if not parent_signal:
    logger.debug("Reply to unknown signal, ignoring",
                parent_msg_id=parent_msg_id)
    return

# NEW: Check sender matches parent signal author
if parent_signal.get('source_user_id') != message.sender_id:
    logger.debug("Reply from different user than signal author, ignoring",
                signal_id=parent_signal['id'],
                sender_id=message.sender_id,
                signal_author=parent_signal.get('source_user_id'))
    return
```

---

## YAML Metadata

```yaml
---
status: SUCCESS
patterns_found: 8
code_examples: 15
categories:
  api: 0
  data: 3
  component: 2
  testing: 1
  state_management: 4
  validation: 3
confidence: high
---
```
