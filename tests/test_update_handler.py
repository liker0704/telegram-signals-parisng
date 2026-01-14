"""Tests for update_handler module - user filtering and flow tracking."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.handlers.update_handler import handle_signal_update


@pytest.fixture
def mock_event():
    """Create a mock Telethon event with required attributes."""
    event = MagicMock()
    message = MagicMock()
    message.id = 123
    message.chat_id = -100111222333
    message.reply_to_msg_id = 100
    message.sender_id = 111
    message.text = "Test reply message"
    message.date = datetime.utcnow()
    message.media = None

    event.message = message
    event.client = AsyncMock()

    return event


@pytest.fixture
def mock_config_allowed():
    """Patch config with allowed_users_list containing test user IDs."""
    with patch('src.handlers.update_handler.config') as mock_config:
        mock_config.allowed_users_list = {111, 222}  # Test user IDs
        yield mock_config


@pytest.fixture
def parent_signal_dict():
    """Create a mock parent signal record."""
    return {
        'id': 1,
        'source_chat_id': -100111222333,
        'source_message_id': 100,
        'source_user_id': 111,
        'original_text': 'BTC/USDT BUY',
        'status': 'POSTED',
        'target_message_id': 999,
        'forward_message_id': None,
        'target_chat_id': -100999888777,
    }


class TestHandleSignalUpdateUserFiltering:
    """Tests for user filtering logic in signal updates."""

    @pytest.mark.asyncio
    async def test_reply_from_same_user_allowed(self, mock_event, parent_signal_dict, mock_config_allowed):
        """Reply from same user as signal author should be allowed (processing continues)."""
        # Setup: sender_id == signal author
        mock_event.message.sender_id = 111
        parent_signal_dict['source_user_id'] = 111

        with patch('src.handlers.update_handler.db_find_update_by_source_msg', new_callable=AsyncMock) as mock_find_update, \
             patch('src.handlers.update_handler.db_find_signal_by_source_msg', new_callable=AsyncMock) as mock_find_signal, \
             patch('src.handlers.update_handler.get_flow_owner', return_value=None) as mock_get_owner, \
             patch('src.handlers.update_handler.start_flow') as mock_start_flow, \
             patch('src.handlers.update_handler.download_and_process_media', new_callable=AsyncMock) as mock_download, \
             patch('src.handlers.update_handler.strip_promo_content', return_value='Clean text') as mock_strip, \
             patch('src.handlers.update_handler.translate_text_with_fallback', new_callable=AsyncMock) as mock_translate, \
             patch('src.handlers.update_handler.process_image', new_callable=AsyncMock) as mock_process_image, \
             patch('src.handlers.update_handler.forward_original_message', new_callable=AsyncMock) as mock_forward, \
             patch('src.handlers.update_handler.is_forwarding_enabled', return_value=False), \
             patch('src.handlers.update_handler.db_insert_signal_update', new_callable=AsyncMock) as mock_insert_update, \
             patch('src.handlers.update_handler.build_final_message', return_value='Final') as mock_build, \
             patch('src.handlers.update_handler.get_publisher_client') as mock_get_publisher, \
             patch('src.handlers.update_handler.db_update_signal_update', new_callable=AsyncMock) as mock_update_signal_update, \
             patch('src.handlers.update_handler.cleanup_media'):

            mock_find_update.return_value = None
            mock_find_signal.return_value = parent_signal_dict
            mock_download.return_value = None
            mock_translate.return_value = 'Translated'
            mock_process_image.return_value = None
            mock_insert_update.return_value = 1

            mock_publisher = AsyncMock()
            mock_posted_msg = MagicMock()
            mock_posted_msg.id = 888
            mock_publisher.send_message.return_value = mock_posted_msg
            mock_get_publisher.return_value = mock_publisher

            # Execute
            await handle_signal_update(mock_event)

            # Verify: should reach the insert step (processing continues)
            mock_insert_update.assert_called_once()
            mock_publisher.send_message.assert_called_once()
            mock_update_signal_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_reply_from_different_user_ignored(self, mock_event, parent_signal_dict, mock_config_allowed):
        """Reply from different user should be ignored (returns early)."""
        # Setup: sender_id != signal author (but in allowed_users)
        mock_event.message.sender_id = 222  # Different user but in allowed_users
        parent_signal_dict['source_user_id'] = 111

        with patch('src.handlers.update_handler.db_find_update_by_source_msg', new_callable=AsyncMock) as mock_find_update, \
             patch('src.handlers.update_handler.db_find_signal_by_source_msg', new_callable=AsyncMock) as mock_find_signal, \
             patch('src.handlers.update_handler.get_flow_owner', return_value=None) as mock_get_owner, \
             patch('src.handlers.update_handler.db_insert_signal_update', new_callable=AsyncMock) as mock_insert_update:

            mock_find_update.return_value = None
            mock_find_signal.return_value = parent_signal_dict

            # Execute
            await handle_signal_update(mock_event)

            # Verify: should NOT reach the insert step (returns early)
            mock_insert_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_hit_same_user_allowed(self, mock_event, parent_signal_dict, mock_config_allowed):
        """Cache hit with matching user should allow processing."""
        mock_event.message.sender_id = 111

        with patch('src.handlers.update_handler.db_find_update_by_source_msg', new_callable=AsyncMock) as mock_find_update, \
             patch('src.handlers.update_handler.db_find_signal_by_source_msg', new_callable=AsyncMock) as mock_find_signal, \
             patch('src.handlers.update_handler.get_flow_owner', return_value=111) as mock_get_owner, \
             patch('src.handlers.update_handler.download_and_process_media', new_callable=AsyncMock) as mock_download, \
             patch('src.handlers.update_handler.strip_promo_content', return_value='Clean text') as mock_strip, \
             patch('src.handlers.update_handler.translate_text_with_fallback', new_callable=AsyncMock) as mock_translate, \
             patch('src.handlers.update_handler.process_image', new_callable=AsyncMock) as mock_process_image, \
             patch('src.handlers.update_handler.forward_original_message', new_callable=AsyncMock) as mock_forward, \
             patch('src.handlers.update_handler.is_forwarding_enabled', return_value=False), \
             patch('src.handlers.update_handler.db_insert_signal_update', new_callable=AsyncMock) as mock_insert_update, \
             patch('src.handlers.update_handler.build_final_message', return_value='Final') as mock_build, \
             patch('src.handlers.update_handler.get_publisher_client') as mock_get_publisher, \
             patch('src.handlers.update_handler.db_update_signal_update', new_callable=AsyncMock) as mock_update_signal_update, \
             patch('src.handlers.update_handler.cleanup_media'):

            mock_find_update.return_value = None
            mock_find_signal.return_value = parent_signal_dict
            mock_download.return_value = None
            mock_translate.return_value = 'Translated'
            mock_process_image.return_value = None
            mock_insert_update.return_value = 1

            mock_publisher = AsyncMock()
            mock_posted_msg = MagicMock()
            mock_posted_msg.id = 888
            mock_publisher.send_message.return_value = mock_posted_msg
            mock_get_publisher.return_value = mock_publisher

            # Execute
            await handle_signal_update(mock_event)

            # Verify: cache hit should allow processing
            mock_insert_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit_different_user_ignored(self, mock_event, parent_signal_dict, mock_config_allowed):
        """Cache hit with different user should reject."""
        mock_event.message.sender_id = 222  # Different user (but in allowed_users)

        with patch('src.handlers.update_handler.db_find_update_by_source_msg', new_callable=AsyncMock) as mock_find_update, \
             patch('src.handlers.update_handler.db_find_signal_by_source_msg', new_callable=AsyncMock) as mock_find_signal, \
             patch('src.handlers.update_handler.get_flow_owner', return_value=111) as mock_get_owner, \
             patch('src.handlers.update_handler.db_insert_signal_update', new_callable=AsyncMock) as mock_insert_update:

            mock_find_update.return_value = None
            mock_find_signal.return_value = parent_signal_dict

            # Execute
            await handle_signal_update(mock_event)

            # Verify: should reject
            mock_insert_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_checks_db_and_populates_cache(self, mock_event, parent_signal_dict, mock_config_allowed):
        """Cache miss should check DB and populate cache for future requests."""
        mock_event.message.sender_id = 111

        with patch('src.handlers.update_handler.db_find_update_by_source_msg', new_callable=AsyncMock) as mock_find_update, \
             patch('src.handlers.update_handler.db_find_signal_by_source_msg', new_callable=AsyncMock) as mock_find_signal, \
             patch('src.handlers.update_handler.get_flow_owner', return_value=None) as mock_get_owner, \
             patch('src.handlers.update_handler.start_flow') as mock_start_flow, \
             patch('src.handlers.update_handler.download_and_process_media', new_callable=AsyncMock) as mock_download, \
             patch('src.handlers.update_handler.strip_promo_content', return_value='Clean text') as mock_strip, \
             patch('src.handlers.update_handler.translate_text_with_fallback', new_callable=AsyncMock) as mock_translate, \
             patch('src.handlers.update_handler.process_image', new_callable=AsyncMock) as mock_process_image, \
             patch('src.handlers.update_handler.forward_original_message', new_callable=AsyncMock) as mock_forward, \
             patch('src.handlers.update_handler.is_forwarding_enabled', return_value=False), \
             patch('src.handlers.update_handler.db_insert_signal_update', new_callable=AsyncMock) as mock_insert_update, \
             patch('src.handlers.update_handler.build_final_message', return_value='Final') as mock_build, \
             patch('src.handlers.update_handler.get_publisher_client') as mock_get_publisher, \
             patch('src.handlers.update_handler.db_update_signal_update', new_callable=AsyncMock) as mock_update_signal_update, \
             patch('src.handlers.update_handler.cleanup_media'):

            mock_find_update.return_value = None
            mock_find_signal.return_value = parent_signal_dict
            mock_download.return_value = None
            mock_translate.return_value = 'Translated'
            mock_process_image.return_value = None
            mock_insert_update.return_value = 1

            mock_publisher = AsyncMock()
            mock_posted_msg = MagicMock()
            mock_posted_msg.id = 888
            mock_publisher.send_message.return_value = mock_posted_msg
            mock_get_publisher.return_value = mock_publisher

            # Execute
            await handle_signal_update(mock_event)

            # Verify: cache miss should check DB (find_signal called) and populate cache
            mock_find_signal.assert_called_once()
            mock_start_flow.assert_called_once_with(1, 111)  # signal_id, user_id

    @pytest.mark.asyncio
    async def test_source_user_id_zero_allowed(self, mock_event, parent_signal_dict):
        """Reply to signal with source_user_id=0 (anonymous) should be allowed."""
        mock_event.message.sender_id = 222  # Any user
        parent_signal_dict['source_user_id'] = 0  # Anonymous sender

        with patch('src.handlers.update_handler.db_find_update_by_source_msg', new_callable=AsyncMock) as mock_find_update, \
             patch('src.handlers.update_handler.db_find_signal_by_source_msg', new_callable=AsyncMock) as mock_find_signal, \
             patch('src.handlers.update_handler.get_flow_owner', return_value=None) as mock_get_owner, \
             patch('src.handlers.update_handler.start_flow') as mock_start_flow, \
             patch('src.handlers.update_handler.download_and_process_media', new_callable=AsyncMock) as mock_download, \
             patch('src.handlers.update_handler.strip_promo_content', return_value='Clean text') as mock_strip, \
             patch('src.handlers.update_handler.translate_text_with_fallback', new_callable=AsyncMock) as mock_translate, \
             patch('src.handlers.update_handler.process_image', new_callable=AsyncMock) as mock_process_image, \
             patch('src.handlers.update_handler.forward_original_message', new_callable=AsyncMock) as mock_forward, \
             patch('src.handlers.update_handler.is_forwarding_enabled', return_value=False), \
             patch('src.handlers.update_handler.db_insert_signal_update', new_callable=AsyncMock) as mock_insert_update, \
             patch('src.handlers.update_handler.build_final_message', return_value='Final') as mock_build, \
             patch('src.handlers.update_handler.get_publisher_client') as mock_get_publisher, \
             patch('src.handlers.update_handler.db_update_signal_update', new_callable=AsyncMock) as mock_update_signal_update, \
             patch('src.handlers.update_handler.cleanup_media'):

            mock_find_update.return_value = None
            mock_find_signal.return_value = parent_signal_dict
            mock_download.return_value = None
            mock_translate.return_value = 'Translated'
            mock_process_image.return_value = None
            mock_insert_update.return_value = 1

            mock_publisher = AsyncMock()
            mock_posted_msg = MagicMock()
            mock_posted_msg.id = 888
            mock_publisher.send_message.return_value = mock_posted_msg
            mock_get_publisher.return_value = mock_publisher

            # Execute
            await handle_signal_update(mock_event)

            # Verify: should allow processing (source_user_id=0 is anonymous)
            mock_insert_update.assert_called_once()
            # Should NOT call start_flow for anonymous (source_user_id <= 0)
            mock_start_flow.assert_not_called()

    @pytest.mark.asyncio
    async def test_source_user_id_none_allowed(self, mock_event, parent_signal_dict):
        """Reply to signal with source_user_id=None (fallback) should be allowed."""
        mock_event.message.sender_id = 333  # Any user
        parent_signal_dict['source_user_id'] = None  # No source user

        with patch('src.handlers.update_handler.db_find_update_by_source_msg', new_callable=AsyncMock) as mock_find_update, \
             patch('src.handlers.update_handler.db_find_signal_by_source_msg', new_callable=AsyncMock) as mock_find_signal, \
             patch('src.handlers.update_handler.get_flow_owner', return_value=None) as mock_get_owner, \
             patch('src.handlers.update_handler.start_flow') as mock_start_flow, \
             patch('src.handlers.update_handler.download_and_process_media', new_callable=AsyncMock) as mock_download, \
             patch('src.handlers.update_handler.strip_promo_content', return_value='Clean text') as mock_strip, \
             patch('src.handlers.update_handler.translate_text_with_fallback', new_callable=AsyncMock) as mock_translate, \
             patch('src.handlers.update_handler.process_image', new_callable=AsyncMock) as mock_process_image, \
             patch('src.handlers.update_handler.forward_original_message', new_callable=AsyncMock) as mock_forward, \
             patch('src.handlers.update_handler.is_forwarding_enabled', return_value=False), \
             patch('src.handlers.update_handler.db_insert_signal_update', new_callable=AsyncMock) as mock_insert_update, \
             patch('src.handlers.update_handler.build_final_message', return_value='Final') as mock_build, \
             patch('src.handlers.update_handler.get_publisher_client') as mock_get_publisher, \
             patch('src.handlers.update_handler.db_update_signal_update', new_callable=AsyncMock) as mock_update_signal_update, \
             patch('src.handlers.update_handler.cleanup_media'):

            mock_find_update.return_value = None
            mock_find_signal.return_value = parent_signal_dict
            mock_download.return_value = None
            mock_translate.return_value = 'Translated'
            mock_process_image.return_value = None
            mock_insert_update.return_value = 1

            mock_publisher = AsyncMock()
            mock_posted_msg = MagicMock()
            mock_posted_msg.id = 888
            mock_publisher.send_message.return_value = mock_posted_msg
            mock_get_publisher.return_value = mock_publisher

            # Execute
            await handle_signal_update(mock_event)

            # Verify: should allow processing (source_user_id=None is fallback)
            mock_insert_update.assert_called_once()
            # Should NOT call start_flow for None
            mock_start_flow.assert_not_called()

    @pytest.mark.asyncio
    async def test_idempotency_skip_already_processed(self, mock_event):
        """Should skip if update was already processed."""
        with patch('src.handlers.update_handler.db_find_update_by_source_msg', new_callable=AsyncMock) as mock_find_update, \
             patch('src.handlers.update_handler.db_find_signal_by_source_msg', new_callable=AsyncMock) as mock_find_signal:

            # Setup: update already exists
            mock_find_update.return_value = {'id': 1, 'status': 'POSTED'}

            # Execute
            await handle_signal_update(mock_event)

            # Verify: should return early without querying for parent signal
            mock_find_update.assert_called_once()
            mock_find_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_parent_message_id_ignored(self, mock_event):
        """Should ignore message that is not a reply (no parent_msg_id)."""
        mock_event.message.reply_to_msg_id = None  # Not a reply

        with patch('src.handlers.update_handler.db_find_update_by_source_msg', new_callable=AsyncMock) as mock_find_update, \
             patch('src.handlers.update_handler.db_find_signal_by_source_msg', new_callable=AsyncMock) as mock_find_signal:

            mock_find_update.return_value = None

            # Execute
            await handle_signal_update(mock_event)

            # Verify: should return early
            mock_find_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_parent_signal_ignored(self, mock_event):
        """Should ignore reply to unknown signal (parent not found)."""
        with patch('src.handlers.update_handler.db_find_update_by_source_msg', new_callable=AsyncMock) as mock_find_update, \
             patch('src.handlers.update_handler.db_find_signal_by_source_msg', new_callable=AsyncMock) as mock_find_signal, \
             patch('src.handlers.update_handler.db_insert_signal_update', new_callable=AsyncMock) as mock_insert_update:

            mock_find_update.return_value = None
            mock_find_signal.return_value = None  # Parent not found

            # Execute
            await handle_signal_update(mock_event)

            # Verify: should return early
            mock_insert_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_parent_not_posted_ignored(self, mock_event, parent_signal_dict):
        """Should ignore if parent signal was not posted to target."""
        parent_signal_dict['target_message_id'] = None  # Not posted

        with patch('src.handlers.update_handler.db_find_update_by_source_msg', new_callable=AsyncMock) as mock_find_update, \
             patch('src.handlers.update_handler.db_find_signal_by_source_msg', new_callable=AsyncMock) as mock_find_signal, \
             patch('src.handlers.update_handler.db_insert_signal_update', new_callable=AsyncMock) as mock_insert_update:

            mock_find_update.return_value = None
            mock_find_signal.return_value = parent_signal_dict

            # Execute
            await handle_signal_update(mock_event)

            # Verify: should return early
            mock_insert_update.assert_not_called()
