# Telegram Authentication Guide

This guide explains how to authenticate the Telegram Signal Translator Bot with your Telegram accounts.

## Overview

The bot requires **two separate Telegram accounts**:
- **Reader Account**: Listens to the source group for trading signals
- **Publisher Account**: Posts translated signals to the target group

## Authentication Methods

### Method 1: StringSession (RECOMMENDED for Docker)

This is the **recommended method** for Docker deployments. Session data is stored as environment variables, avoiding interactive authentication issues in containers.

**Advantages:**
- Works seamlessly in Docker (no interactive input needed)
- Session data stored in `.env` file
- Easy to backup and transfer
- No file mounting complexity

**Disadvantages:**
- Requires local Python setup for initial authentication
- Session strings are long and must be kept secure

#### Setup Steps

**1. Install dependencies locally (outside Docker)**

```bash
pip install telethon python-dotenv
```

**2. Configure your .env file**

```bash
cp .env.example .env
```

Edit `.env` and fill in your API credentials:

```ini
# Reader Account
READER_API_ID=1234567
READER_API_HASH=abcdef123456789abcdef123456789ab
READER_PHONE=+1234567890

# Publisher Account
PUBLISHER_API_ID=9876543
PUBLISHER_API_HASH=zyxwvu987654321zyxwvu987654321zy
PUBLISHER_PHONE=+0987654321
```

**Note:** Get your API credentials from https://my.telegram.org/apps

**3. Run the local authentication script**

```bash
python auth_local.py
```

The script will:
- Prompt you to authenticate the Reader account
- Send a verification code to your Reader account's Telegram app
- Wait for you to enter the code
- Generate a session string for the Reader account
- Repeat the process for the Publisher account
- Display both session strings

**4. Add session strings to .env**

Copy the generated session strings and add them to your `.env` file:

```ini
READER_SESSION_STRING=1BVtsOMGBu7kNWFDM...  # Very long string
PUBLISHER_SESSION_STRING=1BVtsOMGBu8kNWFEM...  # Very long string
```

**5. Start Docker containers**

```bash
docker-compose up -d
```

The bot will now authenticate automatically using the session strings. No interactive input required!

**6. Verify authentication**

```bash
docker-compose logs -f app
```

Look for these log messages:
```
INFO - Initializing Reader client with StringSession
INFO - Reader client connected user_id=123456789 username=myusername session_type=StringSession
INFO - Initializing Publisher client with StringSession
INFO - Publisher client connected user_id=987654321 username=otherusername session_type=StringSession
```

---

### Method 2: File-Based Sessions (Legacy)

This method uses SQLite session files stored on disk. It works for local development but requires interactive authentication on first run.

**Advantages:**
- Simple for local development
- Compatible with standard Telethon examples

**Disadvantages:**
- Requires interactive input on first run (incompatible with Docker by default)
- Session files must be mounted into Docker containers
- More complex backup/transfer process

#### Setup Steps (Local Development Only)

**1. Leave session strings empty in .env**

```ini
# Don't set these:
# READER_SESSION_STRING=
# PUBLISHER_SESSION_STRING=

# Session files will be used instead
READER_SESSION_FILE=sessions/reader.session
PUBLISHER_SESSION_FILE=sessions/publisher.session
```

**2. Run the bot locally**

```bash
python -m src.main
```

**3. Complete interactive authentication**

You'll be prompted to:
- Enter verification codes for both accounts
- Optionally enter 2FA passwords if enabled

**4. Session files are created**

After successful authentication, session files are created:
```
sessions/reader.session
sessions/publisher.session
```

**5. Subsequent runs use the session files**

No authentication needed on future runs - the session files are reused.

---

## Security Considerations

### Session String Security

**Session strings provide FULL ACCESS to your Telegram account**. Treat them like passwords.

**Best Practices:**
- Never commit `.env` to version control (it's in `.gitignore`)
- Store session strings in secure password managers
- Use environment-specific `.env` files (don't reuse production sessions in development)
- Rotate sessions periodically
- Revoke old sessions in Telegram settings when no longer needed

### Revoking Sessions

To revoke a session:

1. Open Telegram app
2. Go to **Settings → Privacy and Security → Active Sessions**
3. Find the session (will be named "Telegram Signal Bot" or similar)
4. Tap **Terminate Session**

After revoking, you'll need to regenerate the session string using `auth_local.py`.

---

## Troubleshooting

### "EOFError: EOF when reading a line"

**Cause:** You're trying to use file-based sessions in Docker without interactive mode.

**Solution:** Use StringSession method instead:
1. Run `python auth_local.py` locally
2. Add generated session strings to `.env`
3. Restart Docker containers

### "READER_SESSION_STRING provided but authorization failed"

**Cause:** The session string is invalid or expired.

**Possible Reasons:**
- Session was revoked in Telegram settings
- Session string was copied incorrectly (truncated or modified)
- Account password was changed
- Session expired (rare, but possible after months of inactivity)

**Solution:**
1. Run `python auth_local.py` to regenerate session strings
2. Update `.env` with new session strings
3. Restart containers

### "Two-factor authentication is enabled"

**Cause:** Your Telegram account has 2FA enabled.

**Solution:** The `auth_local.py` script will prompt you for your 2FA password during authentication. Enter it when requested.

### Session strings in logs

**Warning:** Session strings should NEVER appear in logs. If you see them:
1. Check your logging configuration
2. Ensure `LOG_LEVEL` is not set to `DEBUG` in production
3. Review any custom logging code

---

## Session Management Best Practices

### Development vs Production

Use **different accounts** for development and production:

```bash
# .env.development
READER_SESSION_STRING=1BVtsOMGBu7kNWFDM...  # Dev account
PUBLISHER_SESSION_STRING=1BVtsOMGBu8kNWFEM...  # Dev account

# .env.production
READER_SESSION_STRING=1BVtsOMGBu9kNWFAN...  # Prod account
PUBLISHER_SESSION_STRING=1BVtsOMGBu0kNWFBO...  # Prod account
```

### Backup Sessions

Back up your `.env` file (securely):

```bash
# Encrypt backup
gpg -c .env -o .env.gpg

# Decrypt when needed
gpg -d .env.gpg > .env
```

### Monitoring Active Sessions

Periodically check your active sessions in Telegram:
- **Settings → Privacy and Security → Active Sessions**
- Look for unexpected sessions
- Revoke any suspicious or unused sessions

---

## FAQ

**Q: Can I use the same account for both Reader and Publisher?**
A: No. Telegram doesn't allow a single account to connect from two clients simultaneously. You must use two separate accounts.

**Q: How long do session strings remain valid?**
A: Indefinitely, unless you:
- Explicitly revoke the session
- Change your account password
- Get logged out due to suspicious activity

**Q: Can I use session files in Docker?**
A: Yes, but it's not recommended. You'd need to:
1. Enable interactive mode (`stdin_open: true`, `tty: true`)
2. Run `docker-compose run app` for initial auth
3. Restart in background mode

Use StringSession instead for a simpler workflow.

**Q: What if I lose my session strings?**
A: Simply regenerate them:
1. Run `python auth_local.py`
2. Authenticate again (you'll receive new verification codes)
3. Update `.env` with new session strings

**Q: Are session strings account-specific or device-specific?**
A: Account-specific. You can use the same session string on multiple servers/containers, but be aware that Telegram has rate limits for API usage.

---

## Support

If you encounter issues not covered here:

1. Check logs: `docker-compose logs -f app`
2. Verify `.env` configuration
3. Test authentication locally with `python auth_local.py`
4. Check Telegram API status: https://core.telegram.org/
