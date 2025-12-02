"""Tests for message formatter module."""

import pytest
from src.formatters.message import build_final_message, restore_trading_terms


class TestRestoreTradingTerms:
    """Tests for restore_trading_terms function."""

    def test_restore_tp_spaced(self):
        result = restore_trading_terms("tp 1: 100, tp 2: 200")
        assert "TP1" in result
        assert "TP2" in result

    def test_restore_tp_lowercase(self):
        result = restore_trading_terms("tp1: 100, tp2: 200, tp3: 300")
        assert "TP1" in result
        assert "TP2" in result
        assert "TP3" in result

    def test_restore_sl(self):
        result = restore_trading_terms("sl : 90000")
        assert "SL" in result

    def test_restore_direction_long(self):
        result = restore_trading_terms("direction: long")
        assert "LONG" in result

    def test_restore_direction_short(self):
        result = restore_trading_terms("position short")
        assert "SHORT" in result

    def test_preserve_already_correct(self):
        text = "TP1: 100, TP2: 200, SL: 90, LONG"
        result = restore_trading_terms(text)
        assert "TP1" in result
        assert "TP2" in result
        assert "SL" in result
        assert "LONG" in result


class TestBuildFinalMessage:
    """Tests for build_final_message function."""

    def test_text_only(self):
        result = build_final_message("Translated text")
        assert result == "Translated text"

    def test_with_ocr(self):
        result = build_final_message("Translated text", "OCR from chart")
        assert "Translated text" in result
        assert "Chart OCR" in result
        assert "OCR from chart" in result

    def test_with_none_ocr(self):
        result = build_final_message("Translated text", None)
        assert result == "Translated text"
        assert "OCR" not in result

    def test_with_empty_ocr(self):
        result = build_final_message("Translated text", "")
        # Empty OCR should not add OCR section
        assert result == "Translated text"
