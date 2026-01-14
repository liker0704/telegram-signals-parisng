"""Tests for signal parser module."""

import pytest
from src.parsers.signal_parser import parse_trading_signal, is_signal


class TestIsSignal:
    """Tests for is_signal function."""

    def test_valid_signal(self):
        assert is_signal("#Идея BTC/USDT LONG") is True

    def test_signal_with_other_text(self):
        assert is_signal("Some text #Идея more text") is True

    def test_no_signal_marker(self):
        assert is_signal("BTC/USDT LONG") is False

    def test_empty_string(self):
        assert is_signal("") is False

    def test_none(self):
        assert is_signal(None) is False

    def test_bendi_format_long(self):
        """Test Bendi format with green circle emoji (LONG)."""
        assert is_signal("**FF\n🟢LONG**") is True
        assert is_signal("**BTC 🟢LONG**") is True

    def test_bendi_format_short(self):
        """Test Bendi format with red circle emoji (SHORT)."""
        assert is_signal("**ETH\n🔴SHORT**") is True
        assert is_signal("**SOL 🔴SHORT**") is True

    def test_bendi_format_with_text(self):
        """Test Bendi format with additional text."""
        text = """**FF
🟢LONG**
Вход: 0.123
ТП: 0.15"""
        assert is_signal(text) is True

    def test_bendi_format_case_insensitive(self):
        """Test Bendi format with lowercase direction."""
        assert is_signal("**BTC 🟢long**") is True
        assert is_signal("**BTC 🔴short**") is True


class TestParseTradingSignal:
    """Tests for parse_trading_signal function."""

    def test_full_signal(self):
        text = """#Идея BTC/USDT 4H LONG
Вход: 95000-96000
TP1: $100000
TP2: $105000
TP3: $110000
SL: $90000
Риск: 2%"""
        result = parse_trading_signal(text)

        assert result['pair'] == 'BTC/USDT'
        assert result['direction'] == 'LONG'
        assert result['timeframe'] == '4H'
        assert result['entry_range'] == '95000-96000'
        assert result['tp1'] == 100000.0
        assert result['tp2'] == 105000.0
        assert result['tp3'] == 110000.0
        assert result['sl'] == 90000.0
        assert result['risk_percent'] == 2.0

    def test_partial_signal(self):
        text = "#Идея ETH/USDT SHORT"
        result = parse_trading_signal(text)

        assert result['pair'] == 'ETH/USDT'
        assert result['direction'] == 'SHORT'
        assert result['tp1'] is None
        assert result['sl'] is None

    def test_lowercase_direction(self):
        text = "#Идея BTC/USDT long"
        result = parse_trading_signal(text)
        assert result['direction'] == 'LONG'

    def test_russian_stop_loss(self):
        text = "#Идея Стоп: 50000"
        result = parse_trading_signal(text)
        assert result['sl'] == 50000.0

    def test_timeframe_minutes(self):
        text = "#Идея 15M"
        result = parse_trading_signal(text)
        assert result['timeframe'] == '15M'

    def test_empty_text(self):
        result = parse_trading_signal("")
        assert all(v is None for v in result.values())

    def test_none_text(self):
        result = parse_trading_signal(None)
        assert all(v is None for v in result.values())

    def test_bendi_format_ticker_extraction(self):
        """Test ticker extraction from Bendi format (no slash)."""
        text = "**FF\n🟢LONG**"
        result = parse_trading_signal(text)
        assert result['pair'] == 'FF'
        assert result['direction'] == 'LONG'

    def test_bendi_format_short(self):
        """Test Bendi format with SHORT direction."""
        text = "**BTC 🔴SHORT**"
        result = parse_trading_signal(text)
        assert result['pair'] == 'BTC'
        assert result['direction'] == 'SHORT'

    def test_bendi_format_with_entry(self):
        """Test Bendi format with entry price."""
        text = """**ETH
🟢LONG**
Вход: 3500-3600"""
        result = parse_trading_signal(text)
        assert result['pair'] == 'ETH'
        assert result['direction'] == 'LONG'
        assert result['entry_range'] == '3500-3600'

    def test_bendi_format_lowercase(self):
        """Test Bendi format with lowercase direction."""
        text = "**SOL 🟢long**"
        result = parse_trading_signal(text)
        assert result['pair'] == 'SOL'
        assert result['direction'] == 'LONG'


class TestUnderscorePattern:
    """Tests for underscore pattern (@kvaziroom, user_id: 740952897)"""

    def test_underscore_long(self):
        """Test underscore pattern with LONG direction."""
        assert is_signal("BTC_long", user_id=740952897)

    def test_underscore_short(self):
        """Test underscore pattern with SHORT direction."""
        assert is_signal("ETH_short", user_id=740952897)

    def test_underscore_case_insensitive(self):
        """Test underscore pattern is case-insensitive."""
        assert is_signal("btc_LONG", user_id=740952897)
        assert is_signal("ETH_LONG", user_id=740952897)
        assert is_signal("bTC_sHoRt", user_id=740952897)

    def test_underscore_not_detected_without_user_id(self):
        """Test underscore pattern is NOT detected without user_id (fallback uses hashtag+bendi only)."""
        assert not is_signal("BTC_long")
        assert not is_signal("ETH_short")

    def test_underscore_extraction(self):
        """Test extraction of pair and direction from underscore pattern."""
        # Parse with user_id to use underscore pattern
        result = parse_trading_signal("BTC_long", user_id=740952897)
        assert result['pair'] == 'BTC'
        assert result['direction'] == 'LONG'

        result = parse_trading_signal("ETH_short", user_id=740952897)
        assert result['pair'] == 'ETH'
        assert result['direction'] == 'SHORT'

    def test_underscore_multitoken_pair(self):
        """Test underscore pattern with multi-character token pairs."""
        assert is_signal("DOGE_long", user_id=740952897)
        assert is_signal("SHIB_short", user_id=740952897)

        result = parse_trading_signal("DOGE_long", user_id=740952897)
        assert result['pair'] == 'DOGE'
        assert result['direction'] == 'LONG'


class TestSimplePattern:
    """Tests for simple pattern (@iskeib, user_id: 5575681795)"""

    def test_simple_long(self):
        """Test simple pattern with LONG direction."""
        assert is_signal("BTC LONG", user_id=5575681795)

    def test_simple_short(self):
        """Test simple pattern with SHORT direction."""
        assert is_signal("ETH SHORT", user_id=5575681795)

    def test_simple_case_insensitive(self):
        """Test simple pattern is case-insensitive."""
        assert is_signal("btc long", user_id=5575681795)
        assert is_signal("ETH short", user_id=5575681795)
        assert is_signal("bTC LONG", user_id=5575681795)

    def test_simple_not_detected_without_user_id(self):
        """Test simple pattern is NOT detected without user_id (fallback uses hashtag+bendi only)."""
        assert not is_signal("BTC LONG")
        assert not is_signal("ETH SHORT")

    def test_simple_extraction(self):
        """Test extraction of pair and direction from simple pattern."""
        # Parse with user_id to use simple pattern
        result = parse_trading_signal("BTC LONG", user_id=5575681795)
        assert result['pair'] == 'BTC'
        assert result['direction'] == 'LONG'

        result = parse_trading_signal("ETH SHORT", user_id=5575681795)
        assert result['pair'] == 'ETH'
        assert result['direction'] == 'SHORT'

    def test_simple_multitoken_pair(self):
        """Test simple pattern with multi-character token pairs."""
        assert is_signal("DOGE LONG", user_id=5575681795)
        assert is_signal("SHIB SHORT", user_id=5575681795)

        result = parse_trading_signal("DOGE LONG", user_id=5575681795)
        assert result['pair'] == 'DOGE'
        assert result['direction'] == 'LONG'
