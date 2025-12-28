-- Migration: 002_add_forward_columns.sql
-- Add forward group tracking columns for parallel forwarding feature

-- Add forward columns to signals table
ALTER TABLE signals
ADD COLUMN IF NOT EXISTS forward_chat_id BIGINT,
ADD COLUMN IF NOT EXISTS forward_message_id BIGINT;

-- Add forward columns to signal_updates table
ALTER TABLE signal_updates
ADD COLUMN IF NOT EXISTS forward_chat_id BIGINT,
ADD COLUMN IF NOT EXISTS forward_message_id BIGINT;

-- Create partial index for forward message lookups (for threading)
CREATE INDEX IF NOT EXISTS idx_signals_forward_msg
ON signals(forward_message_id)
WHERE forward_message_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_signal_updates_forward_msg
ON signal_updates(forward_message_id)
WHERE forward_message_id IS NOT NULL;
