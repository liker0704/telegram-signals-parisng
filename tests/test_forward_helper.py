"""Tests for forward_helper module."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.handlers.forward_helper import is_forwarding_enabled, forward_original_message


class TestIsForwardingEnabled:
    """Tests for is_forwarding_enabled function."""

    def test_returns_true_when_configured(self):
        """Should return True when FORWARD_GROUP_ID is set."""
        with patch('src.handlers.forward_helper.config') as mock_config:
            mock_config.FORWARD_GROUP_ID = -100123456789
            assert is_forwarding_enabled() is True

    def test_returns_false_when_not_configured(self):
        """Should return False when FORWARD_GROUP_ID is None."""
        with patch('src.handlers.forward_helper.config') as mock_config:
            mock_config.FORWARD_GROUP_ID = None
            assert is_forwarding_enabled() is False


class TestForwardOriginalMessage:
    """Tests for forward_original_message function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self):
        """Should return (None, None) when forwarding is disabled."""
        with patch('src.handlers.forward_helper.config') as mock_config:
            mock_config.FORWARD_GROUP_ID = None

            result = await forward_original_message(
                original_text="Test message",
                media_path=None
            )

            assert result == (None, None)

    @pytest.mark.asyncio
    async def test_successful_forward(self):
        """Should return (message_id, None) on successful forward."""
        with patch('src.handlers.forward_helper.config') as mock_config, \
             patch('src.handlers.forward_helper.get_publisher_client') as mock_get_client:

            # Setup mocks
            mock_config.FORWARD_GROUP_ID = -100123456789
            mock_config.TIMEOUT_TELEGRAM_SEC = 15

            mock_publisher = AsyncMock()
            mock_posted_msg = MagicMock()
            mock_posted_msg.id = 12345
            mock_publisher.send_message.return_value = mock_posted_msg
            mock_get_client.return_value = mock_publisher

            # Execute
            result = await forward_original_message(
                original_text="Test message",
                media_path=None
            )

            # Verify
            assert result == (12345, None)
            mock_publisher.send_message.assert_called_once_with(
                entity=-100123456789,
                message="Test message",
                file=None,
                reply_to=None
            )

    @pytest.mark.asyncio
    async def test_forward_with_threading(self):
        """Should correctly pass reply_to_forward_id for threading."""
        with patch('src.handlers.forward_helper.config') as mock_config, \
             patch('src.handlers.forward_helper.get_publisher_client') as mock_get_client:

            # Setup mocks
            mock_config.FORWARD_GROUP_ID = -100123456789
            mock_config.TIMEOUT_TELEGRAM_SEC = 15

            mock_publisher = AsyncMock()
            mock_posted_msg = MagicMock()
            mock_posted_msg.id = 67890
            mock_publisher.send_message.return_value = mock_posted_msg
            mock_get_client.return_value = mock_publisher

            # Execute with reply_to_forward_id
            result = await forward_original_message(
                original_text="Reply message",
                media_path=None,
                reply_to_forward_id=54321
            )

            # Verify
            assert result == (67890, None)
            mock_publisher.send_message.assert_called_once_with(
                entity=-100123456789,
                message="Reply message",
                file=None,
                reply_to=54321
            )

    @pytest.mark.asyncio
    async def test_forward_with_media(self):
        """Should correctly pass media_path for images."""
        with patch('src.handlers.forward_helper.config') as mock_config, \
             patch('src.handlers.forward_helper.get_publisher_client') as mock_get_client:

            # Setup mocks
            mock_config.FORWARD_GROUP_ID = -100123456789
            mock_config.TIMEOUT_TELEGRAM_SEC = 15

            mock_publisher = AsyncMock()
            mock_posted_msg = MagicMock()
            mock_posted_msg.id = 11111
            mock_publisher.send_message.return_value = mock_posted_msg
            mock_get_client.return_value = mock_publisher

            # Execute with media
            result = await forward_original_message(
                original_text="Image message",
                media_path="/tmp/image.jpg"
            )

            # Verify
            assert result == (11111, None)
            mock_publisher.send_message.assert_called_once_with(
                entity=-100123456789,
                message="Image message",
                file="/tmp/image.jpg",
                reply_to=None
            )

    @pytest.mark.asyncio
    async def test_handles_timeout(self):
        """Should return (None, error_msg) on timeout."""
        with patch('src.handlers.forward_helper.config') as mock_config, \
             patch('src.handlers.forward_helper.get_publisher_client') as mock_get_client, \
             patch('src.handlers.forward_helper.asyncio.wait_for', new_callable=AsyncMock) as mock_wait_for:

            # Setup mocks
            mock_config.FORWARD_GROUP_ID = -100123456789
            mock_config.TIMEOUT_TELEGRAM_SEC = 15

            mock_publisher = AsyncMock()
            mock_get_client.return_value = mock_publisher

            # Simulate timeout
            mock_wait_for.side_effect = asyncio.TimeoutError()

            # Execute
            result = await forward_original_message(
                original_text="Test message",
                media_path=None
            )

            # Verify
            msg_id, error_msg = result
            assert msg_id is None
            assert error_msg == "Timeout forwarding to forward group"

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        """Should return (None, error_msg) on exception."""
        with patch('src.handlers.forward_helper.config') as mock_config, \
             patch('src.handlers.forward_helper.get_publisher_client') as mock_get_client:

            # Setup mocks
            mock_config.FORWARD_GROUP_ID = -100123456789
            mock_config.TIMEOUT_TELEGRAM_SEC = 15

            mock_publisher = AsyncMock()
            mock_publisher.send_message.side_effect = Exception("Network error")
            mock_get_client.return_value = mock_publisher

            # Execute
            result = await forward_original_message(
                original_text="Test message",
                media_path=None
            )

            # Verify
            msg_id, error_msg = result
            assert msg_id is None
            assert "Failed to forward: Network error" in error_msg

    @pytest.mark.asyncio
    async def test_forward_with_media_and_threading(self):
        """Should handle both media and threading together."""
        with patch('src.handlers.forward_helper.config') as mock_config, \
             patch('src.handlers.forward_helper.get_publisher_client') as mock_get_client:

            # Setup mocks
            mock_config.FORWARD_GROUP_ID = -100123456789
            mock_config.TIMEOUT_TELEGRAM_SEC = 15

            mock_publisher = AsyncMock()
            mock_posted_msg = MagicMock()
            mock_posted_msg.id = 99999
            mock_publisher.send_message.return_value = mock_posted_msg
            mock_get_client.return_value = mock_publisher

            # Execute with both media and reply_to
            result = await forward_original_message(
                original_text="Image reply message",
                media_path="/tmp/chart.png",
                reply_to_forward_id=88888
            )

            # Verify
            assert result == (99999, None)
            mock_publisher.send_message.assert_called_once_with(
                entity=-100123456789,
                message="Image reply message",
                file="/tmp/chart.png",
                reply_to=88888
            )

    @pytest.mark.asyncio
    async def test_forward_uses_correct_timeout(self):
        """Should use TIMEOUT_TELEGRAM_SEC from config."""
        with patch('src.handlers.forward_helper.config') as mock_config, \
             patch('src.handlers.forward_helper.get_publisher_client') as mock_get_client:

            # Setup mocks
            mock_config.FORWARD_GROUP_ID = -100123456789
            mock_config.TIMEOUT_TELEGRAM_SEC = 42  # Custom timeout

            mock_publisher = AsyncMock()
            mock_posted_msg = MagicMock()
            mock_posted_msg.id = 77777

            # Track the timeout used
            original_wait_for = asyncio.wait_for
            timeout_used = None

            async def mock_wait_for_wrapper(coro, timeout):
                nonlocal timeout_used
                timeout_used = timeout
                # Actually await the coroutine to avoid warnings
                return await coro

            mock_publisher.send_message.return_value = mock_posted_msg
            mock_get_client.return_value = mock_publisher

            # Patch wait_for to capture timeout
            with patch('src.handlers.forward_helper.asyncio.wait_for', side_effect=mock_wait_for_wrapper):
                # Execute
                result = await forward_original_message(
                    original_text="Test message",
                    media_path=None
                )

            # Verify timeout was passed correctly
            assert timeout_used == 42
            assert result == (77777, None)
