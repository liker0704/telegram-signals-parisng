-- ==============================================================================
-- Telegram Signal Translator Bot - Initial Database Schema
-- ==============================================================================
-- Migration: 001_init_schema.sql
-- Description: Create initial tables for signal tracking and translation cache
-- ==============================================================================

-- Enable UUID extension (optional, for future use)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==============================================================================
-- Table: signals
-- ==============================================================================
-- Main table for tracking trading signals from source to target group
-- Stores original and translated content, extracted trading fields, and metadata

CREATE TABLE signals (
    id SERIAL PRIMARY KEY,

    -- Source group tracking
    source_chat_id BIGINT NOT NULL,          -- SOURCE_GROUP_ID
    source_message_id BIGINT NOT NULL,       -- Unique per group
    source_user_id BIGINT NOT NULL,          -- Author ID

    -- Target group tracking
    target_chat_id BIGINT,                   -- TARGET_GROUP_ID
    target_message_id BIGINT,                -- Populated after posting

    -- Extracted signal fields (nullable - don't fail if missing)
    pair VARCHAR(20),                        -- e.g., "BTC/USDT"
    direction VARCHAR(10),                   -- "LONG" or "SHORT"
    timeframe VARCHAR(20),                   -- e.g., "15min", "1H", "4H"
    entry_range VARCHAR(50),                 -- e.g., "0.98-0.9283"
    tp1 NUMERIC(20,10),                      -- Take Profit 1
    tp2 NUMERIC(20,10),                      -- Take Profit 2
    tp3 NUMERIC(20,10),                      -- Take Profit 3
    sl NUMERIC(20,10),                       -- Stop Loss
    risk_percent FLOAT,                      -- Risk percentage

    -- Content
    original_text TEXT NOT NULL,             -- Full Russian text
    translated_text TEXT,                    -- Full English translation
    image_source_url TEXT,                   -- Original image URL (from Telegram)
    image_local_path TEXT,                   -- Local path after download
    image_ocr_text TEXT,                     -- Extracted text from image

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(30) DEFAULT 'PENDING',
    error_message TEXT,

    -- Constraints
    CONSTRAINT unique_source_msg UNIQUE (source_chat_id, source_message_id),
    CONSTRAINT check_status CHECK (status IN (
        'PENDING',
        'PROCESSING',
        'POSTED',
        'ERROR_TRANSLATION_FAILED',
        'ERROR_POSTING_FAILED',
        'ERROR_OCR_FAILED'
    )),
    CONSTRAINT check_direction CHECK (direction IS NULL OR direction IN ('LONG', 'SHORT'))
);

-- Indexes for signals table
CREATE INDEX idx_signals_source_msg ON signals(source_chat_id, source_message_id);
CREATE INDEX idx_signals_target_msg ON signals(target_message_id);
CREATE INDEX idx_signals_status ON signals(status);
CREATE INDEX idx_signals_created_at ON signals(created_at DESC);
CREATE INDEX idx_signals_pair ON signals(pair) WHERE pair IS NOT NULL;

-- ==============================================================================
-- Table: signal_updates
-- ==============================================================================
-- Tracks replies and updates to existing signals
-- Linked to parent signal via foreign key

CREATE TABLE signal_updates (
    id SERIAL PRIMARY KEY,

    -- Link to parent signal
    signal_id INTEGER NOT NULL REFERENCES signals(id) ON DELETE CASCADE,

    -- Source reply tracking
    source_chat_id BIGINT NOT NULL,
    source_message_id BIGINT NOT NULL,
    source_user_id BIGINT,

    -- Target reply tracking
    target_chat_id BIGINT,
    target_message_id BIGINT,

    -- Content
    original_text TEXT NOT NULL,
    translated_text TEXT,
    image_source_url TEXT,
    image_local_path TEXT,
    image_ocr_text TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(30) DEFAULT 'PENDING',
    error_message TEXT,

    -- Constraints
    CONSTRAINT unique_source_reply UNIQUE (source_chat_id, source_message_id),
    CONSTRAINT check_update_status CHECK (status IN (
        'PENDING',
        'PROCESSING',
        'POSTED',
        'ERROR_TRANSLATION_FAILED',
        'ERROR_POSTING_FAILED',
        'ERROR_OCR_FAILED'
    ))
);

-- Indexes for signal_updates table
CREATE INDEX idx_signal_updates_parent ON signal_updates(signal_id);
CREATE INDEX idx_signal_updates_source_reply ON signal_updates(source_chat_id, source_message_id);
CREATE INDEX idx_signal_updates_target_msg ON signal_updates(target_message_id);
CREATE INDEX idx_signal_updates_created_at ON signal_updates(created_at DESC);

-- ==============================================================================
-- Table: translation_cache
-- ==============================================================================
-- Caches translations to avoid redundant API calls
-- Uses SHA256 hash of source text for fast lookups

CREATE TABLE translation_cache (
    id SERIAL PRIMARY KEY,

    -- Cache key (hash of source text)
    source_text_hash VARCHAR(64) NOT NULL UNIQUE,

    -- Content
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,

    -- Metadata
    language_pair VARCHAR(10) DEFAULT 'ru_en',  -- Source → Target language
    model VARCHAR(50),                          -- 'gemini-2.0-flash', 'google_translate'

    -- Timestamps and usage
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    usage_count INT DEFAULT 1
);

-- Indexes for translation_cache table
CREATE INDEX idx_translation_cache_hash ON translation_cache(source_text_hash);
CREATE INDEX idx_translation_cache_last_used ON translation_cache(last_used_at DESC);

-- ==============================================================================
-- Helper Functions
-- ==============================================================================

-- Function to update last_used_at and usage_count when cache is hit
CREATE OR REPLACE FUNCTION update_cache_usage()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_used_at = NOW();
    NEW.usage_count = OLD.usage_count + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Note: Trigger would be applied when cache hit logic is implemented
-- CREATE TRIGGER trigger_update_cache_usage
--     BEFORE UPDATE ON translation_cache
--     FOR EACH ROW
--     EXECUTE FUNCTION update_cache_usage();

-- ==============================================================================
-- Initial Data (Optional)
-- ==============================================================================

-- Insert a test record to verify schema (can be deleted after testing)
-- INSERT INTO signals (source_chat_id, source_message_id, source_user_id, original_text, status)
-- VALUES (-100123456789, 1, 123456789, 'Test signal #Идея', 'PENDING');

-- ==============================================================================
-- Comments for documentation
-- ==============================================================================

COMMENT ON TABLE signals IS 'Main table for tracking trading signals from source to target Telegram group';
COMMENT ON TABLE signal_updates IS 'Tracks replies and updates to existing signals, maintaining thread chains';
COMMENT ON TABLE translation_cache IS 'Caches translations to reduce API calls and improve performance';

COMMENT ON COLUMN signals.source_chat_id IS 'Telegram chat ID of the source group (starts with -100)';
COMMENT ON COLUMN signals.target_message_id IS 'Message ID in target group, populated after successful posting';
COMMENT ON COLUMN signals.status IS 'Processing status: PENDING → PROCESSING → POSTED or ERROR_*';
COMMENT ON COLUMN signal_updates.signal_id IS 'Foreign key to parent signal for reply chain tracking';
COMMENT ON COLUMN translation_cache.source_text_hash IS 'SHA256 hash of source_text for fast cache lookups';
