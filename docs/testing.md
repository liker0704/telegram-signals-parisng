# Testing Guide

Comprehensive testing guide for the Telegram Signal Translator Bot. This guide covers unit tests, integration tests, and manual verification procedures.

---

## 1. Testing Overview

The testing strategy is organized into three layers:

### Unit Tests

Isolated tests for individual components with external dependencies mocked:

- **Parsers**: Signal text parsing, regex extraction, field validation
- **Formatters**: Message building, term preservation, text restoration
- **Translators**: Translation logic (with mocked API calls)
- **OCR**: Image text extraction logic (with mocked Gemini Vision)
- **Database Queries**: CRUD operations (with mocked database)

### Integration Tests

Tests that verify component interaction with mocked external services:

- **Handler Integration**: Signal processing pipeline with mocked Telegram/Gemini
- **Database Integration**: Real database operations with test database
- **Translation Pipeline**: End-to-end translation flow with mocked APIs
- **Reply Chain Handling**: Message threading with mocked Telegram clients

### Manual Testing

End-to-end verification in real or staging environment:

- **Signal Detection**: Verify bot detects and processes #Идея messages
- **Translation Quality**: Check accuracy and term preservation
- **Reply Threading**: Verify message chains maintain structure
- **Media Handling**: Test image download and OCR extraction
- **Fallback Mechanisms**: Verify Google Translate fallback works
- **Error Recovery**: Test graceful degradation and retry logic

---

## 2. Pre-Production Checklist

Complete these verification steps before deploying to production:

### Environment Setup

- [ ] Docker and Docker Compose installed
- [ ] PostgreSQL database accessible
- [ ] Redis instance running (optional but recommended)
- [ ] Both Telegram accounts created and verified
- [ ] API credentials obtained for both accounts
- [ ] Gemini API key activated with sufficient quota
- [ ] Google Translate API configured (for fallback)
- [ ] `.env` file configured with all required variables

### Access Verification

- [ ] Reader client connects successfully
- [ ] Reader client can read SOURCE_GROUP messages
- [ ] Publisher client connects successfully
- [ ] Publisher client can write to TARGET_GROUP
- [ ] Both accounts authenticated with valid session files
- [ ] Group IDs verified (start with -100 for groups)

### Core Functionality

- [ ] **Signal detection**: Post message with `#Идея` → appears in target within 60s
- [ ] **Reply handling**: Reply to signal in source → appears as reply in target
- [ ] **Translation quality**: Russian text translates correctly with terms preserved
- [ ] **Image OCR**: Chart image text extracted and translated
- [ ] **Fallback**: Disable Gemini key, verify Google Translate fallback works
- [ ] **Media handling**: Photos are downloaded and re-posted correctly

### Database Verification

- [ ] Database schema initialized correctly
- [ ] `signals` table populates with new signals
- [ ] `signal_updates` table tracks replies correctly
- [ ] `translation_cache` stores and retrieves cached translations
- [ ] Indexes created for performance (idx_source_msg, idx_target_msg)
- [ ] Foreign key constraints working (signal_updates → signals)

### Logging and Monitoring

- [ ] Structured JSON logs appear in output
- [ ] Log level configurable via LOG_LEVEL env var
- [ ] Error messages include full stack traces
- [ ] Metrics logged: latency, success/fail counts, fallback usage
- [ ] Logs accessible via `docker-compose logs app`

### Resilience Testing

- [ ] Docker container restarts successfully after crash
- [ ] Service recovers from temporary network failure
- [ ] Database connection pool recovers from connection loss
- [ ] Telethon clients reconnect after disconnect
- [ ] Failed signals marked in DB with error status

---

## 3. Running Tests

### Unit Tests

Run all unit tests for individual components:

```bash
# Run all unit tests
pytest tests/ -v

# Run specific test file
pytest tests/test_parser.py -v

# Run tests for a specific component
pytest tests/test_parser.py tests/test_formatter.py -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html  # On macOS
xdg-open htmlcov/index.html  # On Linux
```

### Integration Tests

Integration tests require a test database and environment setup:

```bash
# Set up test environment
export ENVIRONMENT=test
export POSTGRES_DB=signal_bot_test

# Run integration tests (requires test database)
pytest tests/integration/ -v --env=test

# Run specific integration test suite
pytest tests/integration/test_handler_integration.py -v

# Run with verbose output for debugging
pytest tests/integration/ -vv --log-cli-level=DEBUG
```

### Test Database Setup

Create a separate test database to avoid polluting production data:

```bash
# Create test database
docker-compose exec db psql -U postgres -c "CREATE DATABASE signal_bot_test;"

# Run schema migrations on test database
docker-compose exec db psql -U postgres -d signal_bot_test -f /migrations/001_init_schema.sql

# Verify tables created
docker-compose exec db psql -U postgres -d signal_bot_test -c "\dt"

# Expected output:
#              List of relations
#  Schema |       Name          | Type  |  Owner
# --------+---------------------+-------+----------
#  public | signals             | table | postgres
#  public | signal_updates      | table | postgres
#  public | translation_cache   | table | postgres
```

### Running Tests in Docker

Run tests inside the Docker container:

```bash
# Run tests in container
docker-compose exec app pytest tests/ -v

# Run with coverage
docker-compose exec app pytest tests/ --cov=src --cov-report=term-missing

# Run integration tests in container
docker-compose exec app pytest tests/integration/ -v --env=test
```

---

## 4. Manual Testing Procedures

### Test 1: Signal Detection and Translation

**Purpose**: Verify basic signal flow from source to target group.

**Steps**:

1. Join SOURCE_GROUP with Reader account
2. Post test message in SOURCE_GROUP:

```
#Идея

BTC/USDT
Таймфрейм: 15мин
Направление: LONG
Вход: 95000-96000
TP1: 100000
TP2: 105000
TP3: 110000
SL: 90000
Риск: 2%

Тестовый сигнал для проверки системы.
```

3. Wait up to 60 seconds
4. Check TARGET_GROUP for translated message

**Expected Result**:

- Message appears in TARGET_GROUP within 60 seconds
- Text translated to English
- Trading terms preserved: `TP1`, `TP2`, `TP3`, `SL`, `LONG`, `BTC/USDT`
- Numbers and price levels unchanged: `95000-96000`, `100000`, etc.
- Emoji preserved (if included)
- Formatting maintained (line breaks, structure)

**Verification**:

```bash
# Check logs for processing
docker-compose logs app | grep "Created signal record"

# Check database
docker-compose exec db psql -U postgres signal_bot -c \
  "SELECT id, pair, direction, status, created_at FROM signals ORDER BY id DESC LIMIT 1;"
```

### Test 2: Reply Threading

**Purpose**: Verify replies maintain threading between source and target groups.

**Steps**:

1. Find a posted signal in SOURCE_GROUP (from previous test)
2. Reply to it with:

```
#Идея

Обновление: TP1 достигнут! Переводим стоп в безубыток.
```

3. Wait for processing
4. Check TARGET_GROUP

**Expected Result**:

- Reply appears in TARGET_GROUP as a threaded reply
- Reply attached to correct parent message
- Translation correct: "Update: TP1 reached! Moving stop to breakeven."
- `#Идея` tag preserved

**Verification**:

```sql
-- Check reply mapping in database
docker-compose exec db psql -U postgres signal_bot -c "
SELECT
  s.id as signal_id,
  s.source_message_id,
  s.target_message_id,
  u.id as update_id,
  u.source_message_id as reply_source,
  u.target_message_id as reply_target
FROM signals s
LEFT JOIN signal_updates u ON u.signal_id = s.id
ORDER BY s.id DESC LIMIT 5;
"
```

### Test 3: Image OCR Extraction

**Purpose**: Verify OCR extracts and translates text from chart images.

**Steps**:

1. Create a TradingView chart screenshot with visible text labels
2. Post in SOURCE_GROUP with signal text:

```
#Идея

BTC/USDT анализ с графиком.
```

3. Attach the chart image
4. Wait for processing
5. Check TARGET_GROUP

**Expected Result**:

- Image downloaded and re-posted in TARGET_GROUP
- OCR text extracted from image
- OCR results included in translated message
- Message format: `[On chart]: [extracted text in English]`

**Verification**:

```bash
# Check logs for OCR processing
docker-compose logs app | grep "OCR"

# Check database for OCR text
docker-compose exec db psql -U postgres signal_bot -c \
  "SELECT id, pair, image_ocr_text FROM signals WHERE image_ocr_text IS NOT NULL ORDER BY id DESC LIMIT 1;"
```

### Test 4: Translation Fallback

**Purpose**: Verify Google Translate fallback when Gemini fails.

**Steps**:

1. Stop the app: `docker-compose stop app`
2. Edit `.env` and set invalid Gemini key: `GEMINI_API_KEY=invalid_key`
3. Restart: `docker-compose up -d app`
4. Post test signal in SOURCE_GROUP
5. Check logs and TARGET_GROUP

**Expected Result**:

- Warning in logs: "Gemini error, falling back to Google Translate"
- Message still posted to TARGET_GROUP
- Translation via Google Translate (may have slightly different quality)
- Trading terms still preserved

**Verification**:

```bash
# Check logs for fallback
docker-compose logs app | grep -i "fallback"

# Restore valid Gemini key after test
# Edit .env and restart: docker-compose restart app
```

### Test 5: Media Download and Posting

**Purpose**: Verify photos are downloaded and re-uploaded correctly.

**Steps**:

1. Post signal with photo attachment:

```
#Идея

Анализ BTC/USDT с графиком.
```

2. Attach any photo (chart screenshot, diagram, etc.)
3. Wait for processing
4. Check TARGET_GROUP

**Expected Result**:

- Photo appears in TARGET_GROUP
- Photo quality preserved
- Photo attached to translated message
- If photo too large (>50MB), graceful failure with log message

**Verification**:

```bash
# Check media download directory
ls -lh /tmp/signals/

# Check database for image paths
docker-compose exec db psql -U postgres signal_bot -c \
  "SELECT id, image_local_path, image_source_url FROM signals WHERE image_local_path IS NOT NULL ORDER BY id DESC LIMIT 3;"
```

### Test 6: Error Recovery and Status Tracking

**Purpose**: Verify failed signals are logged and don't crash the service.

**Steps**:

1. Post signal with malformed target group (edit `.env` temporarily)
2. Post signal when network is disconnected
3. Post signal when database is down
4. Check logs and database status

**Expected Result**:

- Failed signals marked in database with error status
- Error messages logged with stack traces
- Service continues running (doesn't crash)
- Subsequent valid signals still process correctly

**Verification**:

```sql
-- Check failed signals
docker-compose exec db psql -U postgres signal_bot -c "
SELECT id, status, error_message, created_at
FROM signals
WHERE status LIKE 'ERROR%'
ORDER BY id DESC
LIMIT 5;
"
```

### Test 7: Database Integrity

**Purpose**: Verify database constraints and relationships work correctly.

**Steps**:

1. Post several signals and replies
2. Run database integrity checks

**Verification**:

```sql
-- Check for orphaned updates (should return 0)
docker-compose exec db psql -U postgres signal_bot -c "
SELECT COUNT(*)
FROM signal_updates u
LEFT JOIN signals s ON u.signal_id = s.id
WHERE s.id IS NULL;
"

-- Check unique constraints
docker-compose exec db psql -U postgres signal_bot -c "
SELECT source_chat_id, source_message_id, COUNT(*)
FROM signals
GROUP BY source_chat_id, source_message_id
HAVING COUNT(*) > 1;
"
-- Should return 0 rows (no duplicates)

-- Check index usage
docker-compose exec db psql -U postgres signal_bot -c "
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE tablename IN ('signals', 'signal_updates')
ORDER BY idx_scan DESC;
"
```

---

## 5. Test Environment Setup

### Create Isolated Test Environment

Set up a complete test environment separate from production:

```bash
# 1. Create test database
docker-compose exec db psql -U postgres -c "CREATE DATABASE signal_bot_test;"

# 2. Run migrations on test database
docker-compose exec db psql -U postgres -d signal_bot_test -f /migrations/001_init_schema.sql

# 3. Create test .env file
cp .env .env.test

# 4. Edit .env.test with test group IDs
# SOURCE_GROUP_ID=-100111222333  # Test source group
# TARGET_GROUP_ID=-100444555666  # Test target group
# POSTGRES_DB=signal_bot_test

# 5. Run app with test environment
docker-compose run --rm -e POSTGRES_DB=signal_bot_test app python -m src.main
```

### Test Data Fixtures

Create test data for integration tests:

```sql
-- Insert test signal
INSERT INTO signals (
  source_chat_id,
  source_message_id,
  source_user_id,
  pair,
  direction,
  original_text,
  translated_text,
  status,
  target_message_id,
  target_chat_id
) VALUES (
  -100123456789,
  12345,
  987654321,
  'BTC/USDT',
  'LONG',
  'Тестовый сигнал',
  'Test signal',
  'POSTED',
  67890,
  -100987654321
);

-- Insert test reply
INSERT INTO signal_updates (
  signal_id,
  source_chat_id,
  source_message_id,
  original_text,
  translated_text,
  status,
  target_message_id,
  target_chat_id
) VALUES (
  1,  -- Assuming signal_id from above is 1
  -100123456789,
  12346,
  'Обновление',
  'Update',
  'POSTED',
  67891,
  -100987654321
);
```

### Cleanup Test Data

Clean up test data after testing:

```sql
-- Truncate all tables (test database only!)
TRUNCATE TABLE signal_updates CASCADE;
TRUNCATE TABLE signals CASCADE;
TRUNCATE TABLE translation_cache CASCADE;

-- Or drop and recreate database
DROP DATABASE signal_bot_test;
CREATE DATABASE signal_bot_test;
```

---

## 6. Component Verification Table

Quick reference for verifying each component is working correctly:

| Component | How to Verify | Expected Result | Troubleshooting |
|-----------|---------------|-----------------|-----------------|
| **Reader Client** | Check logs: `docker-compose logs app \| grep "Reader has access"` | Group title appears in logs | Check API credentials, verify group ID starts with -100 |
| **Publisher Client** | Check logs: `docker-compose logs app \| grep "Publisher has access"` | Group title appears in logs | Check API credentials, verify write permissions |
| **Signal Detection** | Post `#Идея` message | Message logged: "Created signal record" | Check SOURCE_GROUP_ID, verify account is member |
| **Translation** | Check DB: `SELECT translated_text FROM signals ORDER BY id DESC LIMIT 1;` | English text with preserved terms | Verify Gemini API key, check quotas |
| **OCR** | Check DB: `SELECT image_ocr_text FROM signals WHERE image_ocr_text IS NOT NULL;` | Extracted text populated | Ensure image has readable text, check Gemini Vision API |
| **Reply Chain** | Query: `SELECT target_message_id FROM signal_updates;` | target_message_id maps correctly | Verify idx_source_msg index exists |
| **Fallback** | Set invalid Gemini key, post signal | Google Translate used, logged warning | Check Google Translate API setup |
| **Media Download** | Check `/tmp/signals/` directory | Downloaded images present | Verify MEDIA_DOWNLOAD_DIR exists, check permissions |
| **Database** | Connect: `psql -U postgres signal_bot` | Connection successful | Check POSTGRES_PASSWORD, verify container running |
| **Logs** | Run: `docker-compose logs app \| tail -100` | Structured JSON logs | Check LOG_LEVEL setting |

---

## 7. Common Test Failures

### Failure: "Access verification failed"

**Symptoms**:
- Error in logs: "Access verification failed: 403 Forbidden"
- Bot cannot read SOURCE_GROUP or write to TARGET_GROUP

**Causes**:
- Account not a member of the group
- Incorrect group ID (missing -100 prefix)
- Invalid API credentials

**Solutions**:
```bash
# Verify account is member of groups
# Use Reader account to check SOURCE_GROUP
# Use Publisher account to check TARGET_GROUP

# Verify group IDs
echo $SOURCE_GROUP_ID
echo $TARGET_GROUP_ID
# Both should start with -100

# Test API credentials
docker-compose exec app python -c "
from telethon import TelegramClient
import os
client = TelegramClient('test', os.getenv('READER_API_ID'), os.getenv('READER_API_HASH'))
print('Credentials valid' if client else 'Invalid credentials')
"
```

### Failure: "Translation timeout"

**Symptoms**:
- Error: "Gemini timeout, falling back to Google Translate"
- Slow processing (>30 seconds per signal)

**Causes**:
- Gemini API slow response
- Network latency
- Large text payload

**Solutions**:
```bash
# Increase timeout in .env
TIMEOUT_GEMINI_SEC=45

# Check network connectivity
docker-compose exec app ping -c 3 generativelanguage.googleapis.com

# Verify API key is valid
curl -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"test"}]}]}' \
  "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key=$GEMINI_API_KEY"
```

### Failure: "Reply not threaded"

**Symptoms**:
- Reply posts as new message instead of threaded reply
- target_message_id is NULL in signal_updates table

**Causes**:
- Parent signal not found in database
- source_message_id mapping missing
- Database index not created

**Solutions**:
```sql
-- Verify parent signal exists
SELECT id, source_message_id, target_message_id
FROM signals
WHERE source_message_id = [PARENT_MSG_ID];

-- Check index exists
\d signals
-- Should show index: idx_source_msg

-- Recreate index if missing
CREATE INDEX IF NOT EXISTS idx_source_msg ON signals(source_chat_id, source_message_id);
```

### Failure: "Database connection refused"

**Symptoms**:
- Error: "psycopg2.OperationalError: could not connect to server"
- Service crashes on startup

**Causes**:
- PostgreSQL container not running
- Wrong database credentials
- Database not initialized

**Solutions**:
```bash
# Check PostgreSQL container status
docker-compose ps db

# Start database if stopped
docker-compose up -d db

# Wait for database to be ready
docker-compose exec db pg_isready -U postgres

# Test connection
docker-compose exec db psql -U postgres -c "SELECT version();"

# Verify database exists
docker-compose exec db psql -U postgres -c "\l" | grep signal_bot
```

### Failure: "Session file not found"

**Symptoms**:
- Error: "FileNotFoundError: [Errno 2] No such file or directory: 'reader.session'"
- Authentication required on every restart

**Causes**:
- Session files deleted or not persisted
- Volume mount missing in Docker

**Solutions**:
```bash
# Check session files exist
ls -la *.session

# If missing, authenticate again
docker-compose restart app
# Follow authentication prompts

# Add volume mount to docker-compose.yml to persist sessions
volumes:
  - ./sessions:/app/sessions

# Update .env to use persistent path
READER_SESSION_FILE=/app/sessions/reader.session
PUBLISHER_SESSION_FILE=/app/sessions/publisher.session
```

### Failure: "Image OCR returns 'NO_TEXT_FOUND'"

**Symptoms**:
- OCR extracts no text from chart images
- image_ocr_text is NULL or empty

**Causes**:
- Image has no readable text
- Text too small or blurry
- Gemini Vision API error

**Solutions**:
```bash
# Test with clear, high-contrast image
# Ensure text is at least 12pt font size
# Use TradingView charts with visible labels

# Check Gemini Vision API quota
# Navigate to: https://console.cloud.google.com/apis/api/generativelanguage.googleapis.com/quotas

# Enable detailed OCR logging
LOG_LEVEL=DEBUG
docker-compose restart app
```

---

## 8. Performance Testing

### Latency Benchmarks

Measure end-to-end latency for different scenarios:

```bash
# Test 1: Simple text-only signal
# Expected: 4-8 seconds

# Test 2: Signal with image (no OCR)
# Expected: 8-12 seconds

# Test 3: Signal with image + OCR extraction
# Expected: 10-15 seconds

# Test 4: Reply to existing signal
# Expected: 3-6 seconds

# Monitor latency in logs
docker-compose logs app | grep "latency"
```

### Load Testing

Test system under load:

```bash
# Post 10 signals rapidly (within 1 minute)
# Expected: All process successfully within 60s each

# Monitor resource usage
docker stats

# Check for rate limiting
docker-compose logs app | grep -i "rate"

# Verify all signals posted
docker-compose exec db psql -U postgres signal_bot -c \
  "SELECT COUNT(*) FROM signals WHERE status='POSTED' AND created_at > NOW() - INTERVAL '5 minutes';"
```

### Database Performance

Monitor database query performance:

```sql
-- Enable query logging
ALTER DATABASE signal_bot SET log_statement = 'all';
ALTER DATABASE signal_bot SET log_duration = on;

-- Check slow queries
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Monitor active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'signal_bot';

-- Check table sizes
SELECT
  tablename,
  pg_size_pretty(pg_total_relation_size(tablename::regclass)) AS size
FROM pg_tables
WHERE schemaname = 'public';
```

---

## 9. Continuous Integration

### Automated Test Pipeline

Sample GitHub Actions workflow for automated testing:

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: signal_bot_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run migrations
        run: |
          psql -h localhost -U postgres -d signal_bot_test -f migrations/001_init_schema.sql
        env:
          PGPASSWORD: test_password

      - name: Run unit tests
        run: pytest tests/ -v --cov=src --cov-report=xml

      - name: Run integration tests
        run: pytest tests/integration/ -v
        env:
          POSTGRES_HOST: localhost
          POSTGRES_DB: signal_bot_test
          POSTGRES_PASSWORD: test_password

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 10. Test Documentation

### Writing New Tests

Follow these guidelines when adding tests:

**Unit Test Template**:

```python
# tests/test_signal_parser.py
import pytest
from src.parsers.signal_parser import parse_trading_signal

class TestSignalParser:
    def test_parse_complete_signal(self):
        """Test parsing signal with all fields present."""
        text = """
        #Идея
        BTC/USDT
        Таймфрейм: 15мин
        Направление: LONG
        Вход: 95000-96000
        TP1: 100000
        TP2: 105000
        SL: 90000
        """

        result = parse_trading_signal(text)

        assert result['pair'] == 'BTC/USDT'
        assert result['direction'] == 'LONG'
        assert result['timeframe'] == '15мин'
        assert result['entry_range'] == '95000-96000'
        assert result['tp1'] == 100000.0
        assert result['tp2'] == 105000.0
        assert result['sl'] == 90000.0

    def test_parse_partial_signal(self):
        """Test parsing signal with missing optional fields."""
        text = "#Идея\nBTC/USDT LONG"

        result = parse_trading_signal(text)

        assert result['pair'] == 'BTC/USDT'
        assert result['direction'] == 'LONG'
        assert result['tp1'] is None
        assert result['sl'] is None
```

**Integration Test Template**:

```python
# tests/integration/test_handler_integration.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.handlers.signal_handler import handle_new_signal

@pytest.mark.asyncio
async def test_handle_new_signal_complete_flow(mock_db, mock_telegram_clients):
    """Test complete signal processing flow."""
    # Arrange
    mock_message = MagicMock()
    mock_message.id = 12345
    mock_message.text = "#Идея\nBTC/USDT LONG\nВход: 95000"
    mock_message.photo = None
    mock_message.sender_id = 987654321

    # Act
    await handle_new_signal(mock_message, None)

    # Assert
    # Verify DB insert called
    assert mock_db.insert_signal.called
    # Verify translation called
    assert mock_telegram_clients.publisher.send_message.called
```

---

## Summary

This testing guide provides comprehensive coverage of:

1. **Unit Tests**: Individual component testing with mocked dependencies
2. **Integration Tests**: Multi-component interaction testing
3. **Manual Tests**: End-to-end verification procedures
4. **Pre-Production Checklist**: Complete deployment verification
5. **Component Verification**: Quick reference for health checks
6. **Troubleshooting**: Common issues and solutions
7. **Performance Testing**: Latency and load benchmarks

**Before Production Deployment**:
- Complete all items in Pre-Production Checklist (Section 2)
- Run all automated tests successfully
- Perform manual verification tests (Section 4)
- Monitor logs and metrics during initial operation
- Have rollback plan ready in case of issues

**Ongoing Testing**:
- Run automated tests on every code change
- Perform weekly manual tests in staging environment
- Monitor production metrics and logs daily
- Quarterly performance reviews and load testing

For questions or issues, refer to the main README and technical specification documents.
