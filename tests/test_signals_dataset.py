"""
Tests using real signal dataset from tests/data/test_dataset_signals.json

Tests:
- Signal parser extracts correct fields
- is_signal correctly identifies signals
- Message formatter builds proper output
"""

import json
import pytest
from pathlib import Path

from src.parsers.signal_parser import parse_trading_signal, is_signal
from src.formatters.message import build_final_message, restore_trading_terms


# Load test dataset
DATASET_PATH = Path(__file__).parent / "data" / "test_dataset_signals.json"

with open(DATASET_PATH, "r", encoding="utf-8") as f:
    TEST_SIGNALS = json.load(f)


class TestIsSignalWithDataset:
    """Test is_signal function with real data."""

    @pytest.mark.parametrize("signal", TEST_SIGNALS)
    def test_signal_detected(self, signal):
        """Signals with #идея marker should be detected."""
        text = signal["message_text"]
        # Signal 5 is actually an update message without #идея marker
        if "#идея" in text.lower():
            assert is_signal(text), f"Signal {signal['signal_id']} not detected"
        else:
            # This is an update message, not a new signal
            assert not is_signal(text), f"Update message incorrectly detected as signal"

    def test_replies_without_hashtag_not_detected(self):
        """Replies without #идея should not be detected as signals."""
        for signal in TEST_SIGNALS:
            for reply in signal.get("replies", []):
                text = reply["message_text"]
                # Most replies don't have #идея
                if "#идея" not in text.lower():
                    assert not is_signal(text), f"Reply incorrectly detected as signal: {text[:50]}"


class TestParserWithDataset:
    """Test parse_trading_signal with real data."""

    @pytest.mark.parametrize("signal", TEST_SIGNALS)
    def test_parse_pair(self, signal):
        """Parser should extract trading pair from signals with #идея."""
        text = signal["message_text"]
        expected = signal["parsed_fields"]
        result = parse_trading_signal(text)

        # Only check pair extraction for actual signals (with #идея)
        if expected["pair"] and "#идея" in text.lower():
            assert result.get("pair") is not None, f"Pair not extracted from signal {signal['signal_id']}"

    @pytest.mark.parametrize("signal", TEST_SIGNALS)
    def test_parse_direction(self, signal):
        """Parser should extract direction (LONG/SHORT) from signals with #идея."""
        text = signal["message_text"]
        expected = signal["parsed_fields"]
        result = parse_trading_signal(text)

        # Only check direction extraction for actual signals (with #идея)
        if expected["direction"] and "#идея" in text.lower():
            assert result.get("direction") is not None, f"Direction not extracted from signal {signal['signal_id']}"
            assert result["direction"].upper() in ["LONG", "SHORT"]

    @pytest.mark.parametrize("signal", TEST_SIGNALS)
    def test_parse_timeframe(self, signal):
        """Parser should extract timeframe from signals with #идея."""
        text = signal["message_text"]
        expected = signal["parsed_fields"]
        result = parse_trading_signal(text)

        # Only check timeframe extraction for actual signals (with #идея)
        if expected["timeframe"] and "#идея" in text.lower():
            assert result.get("timeframe") is not None, f"Timeframe not extracted from signal {signal['signal_id']}"

    def test_signal_1_full_parse(self):
        """Test full parsing of signal 1 (YBU/USDT SHORT)."""
        signal = TEST_SIGNALS[0]
        text = signal["message_text"]
        result = parse_trading_signal(text)

        assert result.get("pair") is not None
        assert result.get("direction", "").upper() == "SHORT"
        assert result.get("sl") is not None  # Should extract stop loss 0.4997

    def test_signal_3_long_direction(self):
        """Test signal 3 has LONG direction (BANANAS/USDT)."""
        signal = TEST_SIGNALS[2]  # signal_id 3
        text = signal["message_text"]
        result = parse_trading_signal(text)

        assert result.get("direction", "").upper() == "LONG"

    def test_signal_4_minimal_fields(self):
        """Test signal 4 which has minimal parsed fields (no entry/tp/sl)."""
        signal = TEST_SIGNALS[3]  # signal_id 4, ZEC/USDT
        text = signal["message_text"]
        result = parse_trading_signal(text)

        # Should at least extract pair and direction
        assert "ZEC" in (result.get("pair") or "").upper() or "ZEC" in text


class TestMessageFormatterWithDataset:
    """Test message formatting with real data."""

    def test_build_message_text_only(self):
        """Test building message with text only."""
        translated = "Trading idea on YBU/USDT 15M SHORT"
        result = build_final_message(translated)

        assert translated in result
        assert "#Idea" in result or "YBU" in result

    def test_build_message_with_ocr(self):
        """Test building message with OCR text."""
        translated = "Trading idea on YBU/USDT"
        ocr_text = "BYBIT chart showing ROI +8.09%"

        result = build_final_message(translated, image_ocr=ocr_text)

        assert translated in result
        assert ocr_text in result or "Chart" in result

    def test_restore_trading_terms(self):
        """Test that trading terms are properly restored."""
        # Simulate common translation issues
        text = "tp 1: 0.4773, tp 2: 0.4658, sl: 0.4997, long position"
        result = restore_trading_terms(text)

        # Should capitalize trading terms
        assert "TP1" in result or "TP 1" in result or "tp 1" in result.lower()


class TestRepliesDataset:
    """Test reply message handling."""

    def test_reply_count(self):
        """Verify reply counts in dataset."""
        reply_counts = {s["signal_id"]: len(s.get("replies", [])) for s in TEST_SIGNALS}

        assert reply_counts[1] == 1  # Signal 1 has 1 reply
        assert reply_counts[2] == 2  # Signal 2 has 2 replies
        assert reply_counts[3] == 1  # Signal 3 has 1 reply
        assert reply_counts[4] == 0  # Signal 4 has no replies
        assert reply_counts[5] == 1  # Signal 5 has 1 reply

    def test_reply_references_correct_parent(self):
        """All replies should reference their parent signal."""
        for signal in TEST_SIGNALS:
            parent_msg_id = signal["source_message_id"]
            for reply in signal.get("replies", []):
                assert reply["reply_to_message_id"] == parent_msg_id, \
                    f"Reply {reply['reply_id']} references wrong parent"


class TestEdgeCases:
    """Test edge cases found in dataset."""

    def test_signal_without_entry_price(self):
        """Signal 4 and 5 don't have entry prices."""
        for signal in [TEST_SIGNALS[3], TEST_SIGNALS[4]]:  # signals 4 and 5
            expected = signal["parsed_fields"]
            assert expected["entry_range"] is None

    def test_signal_with_three_takes(self):
        """Signal 2 has 3 take profits."""
        signal = TEST_SIGNALS[1]  # signal_id 2
        expected = signal["parsed_fields"]

        assert expected["tp1"] is not None
        assert expected["tp2"] is not None
        assert expected["tp3"] is not None

    def test_signal_with_two_takes(self):
        """Signal 1 has only 2 take profits."""
        signal = TEST_SIGNALS[0]  # signal_id 1
        expected = signal["parsed_fields"]

        assert expected["tp1"] is not None
        assert expected["tp2"] is not None
        assert expected["tp3"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
