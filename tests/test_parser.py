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
