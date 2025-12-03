# Quick Start Guide - Telegram Signal Translator Bot

Get up and running in 5 minutes!

## Prerequisites

- Python 3.11+ installed locally
- Docker and Docker Compose installed
- Two separate Telegram accounts
- API credentials from https://my.telegram.org/apps
- Gemini API key from https://makersuite.google.com/app/apikey

---

## Step 1: Clone and Configure (2 minutes)

```bash
# Clone repository
git clone https://github.com/yourusername/telegram-signals-parisng.git
cd telegram-signals-parisng

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env  # or your preferred editor
```

Fill in these required values in `.env`:
```ini
# Reader Account
READER_API_ID=YOUR_API_ID
READER_API_HASH=YOUR_API_HASH
READER_PHONE=+1234567890

# Publisher Account
PUBLISHER_API_ID=YOUR_API_ID
PUBLISHER_API_HASH=YOUR_API_HASH
PUBLISHER_PHONE=+0987654321

# Groups
SOURCE_GROUP_ID=-100123456789
TARGET_GROUP_ID=-100987654321

# Gemini
GEMINI_API_KEY=AIzaSy...

# Database
POSTGRES_PASSWORD=choose_secure_password
```

---

## Step 2: Authenticate Accounts (2 minutes)

```bash
# Install local dependencies
pip install telethon python-dotenv

# Run authentication script
python auth_local.py
```

Follow the prompts:
1. You'll receive a code in Reader account's Telegram → enter it
2. You'll receive a code in Publisher account's Telegram → enter it
3. Script outputs session strings

Copy the session strings and add to your `.env`:
```ini
READER_SESSION_STRING=1BVtsOMGBu7kNWFDM...
PUBLISHER_SESSION_STRING=1BVtsOMGBu8kNWFEM...
```

---

## Step 3: Start the Bot (1 minute)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app
```

Look for these success messages:
```
INFO - Reader client connected user_id=123456789 session_type=StringSession
INFO - Publisher client connected user_id=987654321 session_type=StringSession
INFO - Bot started successfully. Listening for signals...
```

---

## Step 4: Test It Out!

Post this test message in your **SOURCE_GROUP**:

```
#Идея

BTC/USDT
Timeframe: 15мин
Direction: LONG
Entry: 65000-65500
TP1: 66000
TP2: 67000
SL: 64000
Risk: 2%

Тестовый сигнал для проверки.
```

Within 60 seconds, you should see the translated version in your **TARGET_GROUP**:

```
#Idea

BTC/USDT
Timeframe: 15min
Direction: LONG
Entry: 65000-65500
TP1: 66000
TP2: 67000
SL: 64000
Risk: 2%

Test signal for verification.
```

---

## Troubleshooting

### Bot not receiving messages?
```bash
# Check logs
docker-compose logs -f app

# Verify Reader account is in SOURCE_GROUP
# Verify SOURCE_GROUP_ID is correct (should start with -100)
```

### Authentication failed?
```bash
# Regenerate session strings
python auth_local.py

# Update .env with new strings
# Restart containers
docker-compose restart app
```

### Translation not working?
```bash
# Check Gemini API key is valid
# Check logs for translation errors
docker-compose logs -f app | grep -i "error\|gemini"
```

### Database issues?
```bash
# Check database is running
docker-compose ps db

# View database logs
docker-compose logs db

# Restart database
docker-compose restart db
```

---

## Management Commands

```bash
# Stop the bot
docker-compose down

# Restart the bot
docker-compose restart app

# View all logs
docker-compose logs

# Follow live logs
docker-compose logs -f app

# Check service status
docker-compose ps

# Access database
docker-compose exec db psql -U postgres signal_bot

# Remove all data (DANGER!)
docker-compose down -v
```

---

## Next Steps

- Read [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) for session management
- Review [README.md](README.md) for complete documentation
- Check [.env.example](.env.example) for all configuration options
- Join our community for support

---

## Security Checklist

- [ ] `.env` is in `.gitignore` (never commit it!)
- [ ] Session strings are kept secret
- [ ] PostgreSQL has a strong password
- [ ] Only authorized users can post signals (SOURCE_ALLOWED_USERS)
- [ ] Accounts have 2FA enabled in Telegram
- [ ] Regular session audits in Telegram settings

---

**That's it!** Your bot is now running and ready to translate signals.

Happy trading! 🚀
