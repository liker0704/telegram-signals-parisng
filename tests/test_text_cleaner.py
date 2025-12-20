"""Tests for text_cleaner utility."""

import pytest
from src.utils.text_cleaner import strip_promo_content, contains_promo_content


class TestStripPromoContent:
    """Tests for strip_promo_content function."""

    def test_removes_tribute_donation_link(self):
        """Should remove tribute.app donation links."""
        text = """Тейк взяли 🔥

🟢[**Отправить донат Марку**](https://t.me/tribute/app?startapp=dy1V)"""
        result = strip_promo_content(text)
        assert "tribute" not in result
        assert "донат" not in result
        assert "Тейк взяли 🔥" in result

    def test_removes_maxmotruk_training_link(self):
        """Should remove maxmotruk.com training links."""
        text = """Стоп в бу 🔄

[**Пройти обучение**](https://maxmotruk.com/trading-chat)"""
        result = strip_promo_content(text)
        assert "maxmotruk" not in result
        assert "обучение" not in result
        assert "Стоп в бу 🔄" in result

    def test_removes_multiple_promo_links(self):
        """Should remove both donation and training links."""
        text = """Забрали тейк 🔥

**🟢**** **[**Отправить донат Марку**](https://t.me/tribute/app?startapp=dy1V)** | ****🟢**** **[**Пройти обучение**](https://maxmotruk.com/trading-chat)"""
        result = strip_promo_content(text)
        assert "tribute" not in result
        assert "maxmotruk" not in result
        assert "Забрали тейк 🔥" in result

    def test_preserves_normal_trading_signal(self):
        """Should not modify normal trading signals without promo."""
        text = """#Идея LIGHT/USDT 4Ч

LONG 📈

Диапазон входа: 2.17-2.11$

• TP1: $2.21
• TP2: $2.35"""
        result = strip_promo_content(text)
        assert result == text

    def test_preserves_other_telegram_links(self):
        """Should not remove non-promo Telegram links."""
        text = "Смотри канал [TradingView](https://t.me/tradingview)"
        result = strip_promo_content(text)
        assert "tradingview" in result.lower()

    def test_handles_empty_string(self):
        """Should handle empty string."""
        assert strip_promo_content("") == ""

    def test_handles_none(self):
        """Should handle None input."""
        assert strip_promo_content(None) is None

    def test_cleans_green_emoji_formatting(self):
        """Should clean up leftover green emoji formatting."""
        text = """Тейк 🔥

**🟢**** **[**Отправить донат**](https://t.me/tribute/app?startapp=x)"""
        result = strip_promo_content(text)
        assert "🟢" not in result
        assert "****" not in result


class TestContainsPromoContent:
    """Tests for contains_promo_content function."""

    def test_detects_tribute_link(self):
        """Should detect tribute.app links."""
        text = "[Donate](https://t.me/tribute/app?startapp=x)"
        assert contains_promo_content(text) is True

    def test_detects_maxmotruk_link(self):
        """Should detect maxmotruk.com links."""
        text = "[Training](https://maxmotruk.com/course)"
        assert contains_promo_content(text) is True

    def test_returns_false_for_clean_text(self):
        """Should return False for text without promo."""
        text = "#Идея BTC/USDT LONG"
        assert contains_promo_content(text) is False

    def test_handles_empty_string(self):
        """Should return False for empty string."""
        assert contains_promo_content("") is False
