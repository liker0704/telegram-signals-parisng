# Telegram Signal Translator Bot

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Telethon](https://img.shields.io/badge/telethon-1.36%2B-orange)

An asynchronous backend service that reads trading signals from a Russian Telegram group, translates them to English using Google Gemini AI, and posts them to an English Telegram group while maintaining message threading and reply chains.

## Features

- **Dual-Account Architecture**: Uses two separate Telegram user accounts (Reader + Publisher) via MTProto Client API
- **Real-Time Signal Detection**: Automatically detects trading signals tagged with `#Идея` in source group
- **AI-Powered Translation**: Translates Russian text to English using Google Gemini 2.0 Flash API
- **Intelligent OCR**: Extracts and translates text from trading chart images using Gemini Vision
- **Message Threading**: Preserves reply chains between source and target groups
- **Structured Data Extraction**: Parses trading pairs, entry/exit points, TP/SL levels, risk percentage
- **Fallback Translation**: Automatically falls back to Google Translate if Gemini API fails
- **Low Latency**: Achieves <60 second end-to-end latency from signal detection to posting
- **PostgreSQL Persistence**: Stores signal history and message mappings
- **Translation Caching**: Reduces API costs by caching translations
- **Docker Ready**: Single-command deployment with Docker Compose

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYSTEM ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────┘

Account A (Reader)            Core Logic              Account B (Publisher)
Telethon Client 1         PostgreSQL + Redis         Telethon Client 2
     ↓                         ↓                           ↑
Listen to                process_signal()            Send to
SOURCE_GROUP            translate_text()          TARGET_GROUP
                        handle_replies()
                        map_message_ids()

Events:                  Pipeline:
- new_message           1. Parse signal (#Идея)
- message_edited        2. Download media
- reply detected        3. Gemini: translate + OCR (parallel)
     ↓                  4. Cache translations
Async queue             5. Publish to target group
(asyncio.Queue)         6. Store mapping in DB
                        7. Handle replies with threading
```

## Project Structure

```
telegram-signals-parisng/
├── src/
│   ├── main.py                    # Entry point, initialize clients
│   ├── config.py                  # Configuration loader
│   ├── db/
│   │   ├── connection.py          # PostgreSQL connection pool
│   │   └── queries.py             # Database operations
│   ├── handlers/
│   │   ├── signal_handler.py      # New signal processing
│   │   └── update_handler.py      # Reply/update handling
│   ├── translators/
│   │   ├── gemini.py              # Gemini API translation
│   │   ├── google.py              # Google Translate fallback
│   │   └── fallback.py            # Translation with fallback logic
│   ├── ocr/
│   │   └── gemini_ocr.py          # Image OCR processing
│   ├── media/
│   │   └── downloader.py          # Media download handler
│   ├── parsers/
│   │   └── signal_parser.py       # Trading signal parser
│   ├── formatters/
│   │   └── message.py             # Message formatting
│   └── utils/
│       └── logger.py              # Structured logging
├── migrations/
│   └── 001_init_schema.sql        # Database schema
├── docker-compose.yml              # Docker orchestration
├── Dockerfile                      # Container image
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
└── README.md                       # This file
```

## Quick Start

### Prerequisites

- **Python 3.11+** (for local development)
- **Docker** and **Docker Compose** (for containerized deployment)
- **Telegram User Accounts**: Two separate accounts with API credentials
  - Get API credentials from [my.telegram.org](https://my.telegram.org/apps)
- **Google Gemini API Key**: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
- **PostgreSQL 15+** (provided via Docker)

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/telegram-signals-parisng.git
cd telegram-signals-parisng
```

2. **Configure environment variables**

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```ini
# Reader Account (Listens to source group)
READER_API_ID=your_api_id
READER_API_HASH=your_api_hash
READER_PHONE=+1234567890

# Publisher Account (Posts to target group)
PUBLISHER_API_ID=your_api_id
PUBLISHER_API_HASH=your_api_hash
PUBLISHER_PHONE=+0987654321

# Group IDs (use @username_to_id_bot to get IDs)
SOURCE_GROUP_ID=-100123456789
TARGET_GROUP_ID=-100987654321

# Gemini API
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.0-flash

# Database
POSTGRES_PASSWORD=secure_password_here
```

3. **Run with Docker Compose**

```bash
docker-compose up -d
```

The service will:
- Start PostgreSQL and Redis containers
- Initialize database schema
- Authenticate both Telegram accounts (you'll receive verification codes via Telegram)
- Begin listening for signals in the source group

4. **View logs**

```bash
# Follow live logs
docker-compose logs -f app

# Check all services
docker-compose ps
```

### First Time Setup

**IMPORTANT:** You must generate session strings BEFORE running Docker:

1. **Install dependencies locally** (outside Docker):
   ```bash
   pip install telethon python-dotenv
   ```

2. **Run the authentication script**:
   ```bash
   python auth_local.py
   ```

3. **Follow the prompts**:
   - Authenticate Reader account (you'll receive a Telegram code)
   - Authenticate Publisher account (you'll receive another code)
   - Script will output session strings

4. **Add session strings to .env**:
   ```ini
   READER_SESSION_STRING=1BVtsOMGBu7kNWFDM...
   PUBLISHER_SESSION_STRING=1BVtsOMGBu8kNWFEM...
   ```

5. **Start Docker containers**:
   ```bash
   docker-compose up -d
   ```

Session strings remain valid indefinitely. No interactive authentication needed in Docker!

For detailed authentication instructions, see [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md)

### Testing

Post a test message in your source group:

```
#Идея

BTC/USDT
Timeframe: 15мин
Direction: LONG
Entry: 65000-65500
TP1: 66000
TP2: 67000
TP3: 68000
SL: 64000
Risk: 2%

Test signal for verification
```

The bot should translate and post it to the target group within 60 seconds.

## Configuration Reference

See [.env.example](.env.example) for complete configuration options including:

- **Telegram Accounts**: API credentials and session management
- **Group Settings**: Source/target group IDs, user whitelist
- **Translation**: Gemini API settings, timeouts, model selection
- **Database**: PostgreSQL connection parameters
- **Media**: Download directory, size limits
- **Logging**: Log levels, structured logging options

### Key Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `SOURCE_GROUP_ID` | Telegram group to monitor for signals | Required |
| `TARGET_GROUP_ID` | Telegram group to post translations | Required |
| `GEMINI_MODEL` | Gemini model (2.0-flash or 1.5-pro) | `gemini-2.0-flash` |
| `TIMEOUT_GEMINI_SEC` | Max timeout for Gemini API calls | `30` |
| `MAX_IMAGE_SIZE_MB` | Maximum image size to process | `50` |
| `LOG_LEVEL` | Logging verbosity (DEBUG/INFO/WARNING/ERROR) | `INFO` |

## How It Works

### Signal Detection

1. **Reader Account** listens to `SOURCE_GROUP_ID` for new messages
2. Messages containing `#Идея` are identified as trading signals
3. Message content and metadata are extracted

### Translation Pipeline

1. **Text Translation**: Russian text → English via Gemini API
2. **Image Processing**: Download chart images and run OCR extraction
3. **Parallel Processing**: Text and OCR run concurrently for speed
4. **Fallback**: If Gemini fails, falls back to Google Translate
5. **Preservation**: Trading terms (TP1, SL, LONG, SHORT) remain untranslated

### Publishing

1. **Formatting**: Combine translated text with OCR results
2. **Posting**: Publisher account sends message to `TARGET_GROUP_ID`
3. **Mapping**: Store source→target message ID mapping in database
4. **Threading**: Replies to signals are posted as threaded replies

### Reply Handling

1. Detect when a message is a reply to an existing signal
2. Look up parent signal's target message ID from database
3. Translate and post as a threaded reply in target group
4. Maintain clean reply chains across both groups

## Database Schema

The service uses PostgreSQL with three main tables:

- **signals**: Main signal records with translations and mappings
- **signal_updates**: Reply/update records linked to parent signals
- **translation_cache**: Cache for repeated translations (reduces API costs)

See [migrations/001_init_schema.sql](migrations/001_init_schema.sql) for complete schema.

## Performance

**Target Latency**: <60 seconds from source post to target post

**Typical Breakdown**:
- Event detection: <100ms
- Parsing + extraction: <200ms
- Media download: 500ms - 2s
- Gemini API translation: 3-8s
- Image OCR: 2-5s (parallel)
- Posting to target: 500ms - 1s
- **Total: ~6-12 seconds** ✅

## Monitoring & Logs

The service produces structured JSON logs with:

- Signal received/processed events
- Translation API calls and latency
- Database operations
- Error traces with full context

**Key Metrics Logged**:
- `avg_latency_seconds`: End-to-end processing time
- `signals_processed_total`: Count of successful signals
- `signals_failed_total`: Count of failures
- `translation_fallback_count`: Gemini→Google Translate fallbacks
- `image_ocr_success_rate`: OCR extraction success rate

## Error Handling

The service implements robust error handling:

- **Translation Failures**: Falls back to Google Translate, then posts original text
- **Image OCR Failures**: Posts signal without OCR text
- **Network Errors**: Retries with exponential backoff (up to 3 attempts)
- **Database Errors**: Logs error, marks signal as failed, continues operation
- **Account Disconnects**: Automatic reconnection with backoff

Failed signals are marked in the database with error status and messages for debugging.

## Troubleshooting

### Bot not receiving messages

- Verify Reader account is a member of SOURCE_GROUP
- Check `SOURCE_GROUP_ID` is correct (should start with `-100`)
- Ensure Reader account has read permissions

### Translation not working

- Check Gemini API key is valid
- Verify API quotas haven't been exceeded
- Check logs for translation errors
- Test fallback: temporarily disable Gemini to verify Google Translate works

### Messages not posting to target

- Verify Publisher account is a member of TARGET_GROUP
- Check Publisher account has write permissions
- Ensure TARGET_GROUP allows user posts (not read-only)

### Database connection issues

```bash
# Check PostgreSQL is running
docker-compose ps db

# Test connection
docker-compose exec db psql -U postgres signal_bot

# View logs
docker-compose logs db
```

### Session authentication issues

- Delete session files: `rm *.session`
- Restart service: `docker-compose restart app`
- Re-authenticate when prompted

## Development

### Local Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
psql -U postgres signal_bot < migrations/001_init_schema.sql

# Run application
python -m src.main
```

### Running Tests

```bash
# Unit tests
pytest tests/

# Integration tests
pytest tests/integration/

# With coverage
pytest --cov=src tests/
```

## Security Considerations

- **Session Files**: Keep `.session` files secure (they provide account access)
- **API Keys**: Never commit `.env` to version control
- **Database**: Use strong passwords for production deployments
- **Network**: Consider running in a private network/VPN
- **Rate Limiting**: Gemini API has rate limits; monitor usage

## Known Limitations

- Supports one source and one target group (could extend to multiple)
- No web dashboard for manual intervention
- Session files stored locally (could use encrypted remote storage)
- No support for edited messages (only new messages and replies)

## Future Enhancements

- Web dashboard to view signal history and statistics
- Admin panel to retry failed translations
- Support for multiple source/target group pairs
- Real-time analytics and performance metrics
- Webhook mode as alternative to polling
- Support for message edits in source group

## License

MIT License - see [LICENSE](LICENSE) for details

## Support

For issues or questions:

1. Check logs: `docker-compose logs app`
2. Verify database: `docker-compose exec db psql -U postgres signal_bot`
3. Test API keys: Verify Gemini API works with a simple test call
4. Restart service: `docker-compose restart app`

---

**Built with**: Telethon, Google Gemini AI, PostgreSQL, Docker
