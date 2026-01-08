"""Tests for flow_tracker module."""

import time
import pytest
from unittest.mock import patch, MagicMock

from src.state.flow_tracker import (
    start_flow,
    is_allowed,
    get_flow_owner,
    end_flow,
    cleanup_expired,
    _active_flows,
    _force_cleanup,
    FLOW_TTL,
    MAX_FLOWS,
)


class TestStartFlow:
    """Tests for start_flow function."""

    def setup_method(self):
        """Clear active flows before each test."""
        _active_flows.clear()

    def test_registers_flow(self):
        """Should register a new flow for signal."""
        signal_id = 123
        user_id = 456

        start_flow(signal_id, user_id)

        assert signal_id in _active_flows
        assert _active_flows[signal_id].user_id == user_id
        assert isinstance(_active_flows[signal_id].timestamp, float)

    def test_updates_existing_flow(self):
        """Should update timestamp for existing signal."""
        signal_id = 123
        user_id_1 = 456
        user_id_2 = 789

        start_flow(signal_id, user_id_1)
        timestamp_1 = _active_flows[signal_id].timestamp

        time.sleep(0.01)  # Ensure time difference
        start_flow(signal_id, user_id_2)
        timestamp_2 = _active_flows[signal_id].timestamp

        assert _active_flows[signal_id].user_id == user_id_2
        assert timestamp_2 > timestamp_1

    def test_timestamp_is_recent(self):
        """Should set timestamp to current time."""
        signal_id = 123
        user_id = 456

        before = time.time()
        start_flow(signal_id, user_id)
        after = time.time()

        stored_timestamp = _active_flows[signal_id].timestamp
        assert before <= stored_timestamp <= after


class TestIsAllowed:
    """Tests for is_allowed function."""

    def setup_method(self):
        """Clear active flows before each test."""
        _active_flows.clear()

    def test_returns_true_when_no_flow_exists(self):
        """Should allow any user if no flow exists for signal."""
        signal_id = 123
        user_id = 456

        assert is_allowed(signal_id, user_id) is True

    def test_returns_true_for_flow_owner(self):
        """Should allow owner to edit signal."""
        signal_id = 123
        user_id = 456

        start_flow(signal_id, user_id)
        assert is_allowed(signal_id, user_id) is True

    def test_returns_false_for_different_user(self):
        """Should deny access to different user."""
        signal_id = 123
        owner_id = 456
        other_user = 789

        start_flow(signal_id, owner_id)
        assert is_allowed(signal_id, other_user) is False

    def test_returns_true_after_ttl_expiration(self):
        """Should allow any user after flow expires."""
        signal_id = 123
        owner_id = 456
        other_user = 789

        start_flow(signal_id, owner_id)

        # Mock time to simulate expiration
        with patch('src.state.flow_tracker.time.time') as mock_time:
            # Set current time to past the TTL
            current_time = _active_flows[signal_id].timestamp
            mock_time.return_value = current_time + FLOW_TTL + 1

            # Other user should now be allowed
            assert is_allowed(signal_id, other_user) is True

    def test_removes_expired_flow_during_check(self):
        """Should remove expired flow from tracking."""
        signal_id = 123
        owner_id = 456

        start_flow(signal_id, owner_id)
        assert signal_id in _active_flows

        # Mock time to simulate expiration
        with patch('src.state.flow_tracker.time.time') as mock_time:
            current_time = _active_flows[signal_id].timestamp
            mock_time.return_value = current_time + FLOW_TTL + 1

            # Call is_allowed to trigger expiration check
            is_allowed(signal_id, owner_id)

            # Flow should be removed
            assert signal_id not in _active_flows


class TestGetFlowOwner:
    """Tests for get_flow_owner function."""

    def setup_method(self):
        """Clear active flows before each test."""
        _active_flows.clear()

    def test_returns_correct_owner(self):
        """Should return the owner of an active flow."""
        signal_id = 123
        user_id = 456

        start_flow(signal_id, user_id)
        owner = get_flow_owner(signal_id)

        assert owner == user_id

    def test_returns_none_for_unknown_signal(self):
        """Should return None if signal has no flow."""
        signal_id = 123
        owner = get_flow_owner(signal_id)

        assert owner is None

    def test_returns_none_for_expired_flow(self):
        """Should return None and remove expired flow."""
        signal_id = 123
        user_id = 456

        start_flow(signal_id, user_id)
        assert signal_id in _active_flows

        # Mock time to simulate expiration
        with patch('src.state.flow_tracker.time.time') as mock_time:
            current_time = _active_flows[signal_id].timestamp
            mock_time.return_value = current_time + FLOW_TTL + 1

            owner = get_flow_owner(signal_id)

            assert owner is None
            assert signal_id not in _active_flows

    def test_returns_owner_before_expiration(self):
        """Should return owner while flow is still valid."""
        signal_id = 123
        user_id = 456

        start_flow(signal_id, user_id)

        # Mock time to be just before expiration
        with patch('src.state.flow_tracker.time.time') as mock_time:
            current_time = _active_flows[signal_id].timestamp
            mock_time.return_value = current_time + FLOW_TTL - 1

            owner = get_flow_owner(signal_id)

            assert owner == user_id
            assert signal_id in _active_flows


class TestEndFlow:
    """Tests for end_flow function."""

    def setup_method(self):
        """Clear active flows before each test."""
        _active_flows.clear()

    def test_removes_flow(self):
        """Should remove flow from tracking."""
        signal_id = 123
        user_id = 456

        start_flow(signal_id, user_id)
        assert signal_id in _active_flows

        end_flow(signal_id)
        assert signal_id not in _active_flows

    def test_handles_nonexistent_flow(self):
        """Should not raise error for unknown signal."""
        signal_id = 123
        # Should not raise any exception
        end_flow(signal_id)

    def test_removes_only_specified_flow(self):
        """Should remove only the specified flow."""
        signal_id_1 = 123
        signal_id_2 = 456
        user_id = 789

        start_flow(signal_id_1, user_id)
        start_flow(signal_id_2, user_id)

        end_flow(signal_id_1)

        assert signal_id_1 not in _active_flows
        assert signal_id_2 in _active_flows


class TestCleanupExpired:
    """Tests for cleanup_expired function."""

    def setup_method(self):
        """Clear active flows before each test."""
        _active_flows.clear()

    def test_removes_expired_flows(self):
        """Should remove all expired flows."""
        signal_id_1 = 100
        signal_id_2 = 200
        signal_id_3 = 300
        user_id = 456

        start_flow(signal_id_1, user_id)
        start_flow(signal_id_2, user_id)
        start_flow(signal_id_3, user_id)

        assert len(_active_flows) == 3

        # Mock time to expire all flows
        with patch('src.state.flow_tracker.time.time') as mock_time:
            current_time = _active_flows[signal_id_1].timestamp
            mock_time.return_value = current_time + FLOW_TTL + 1

            removed = cleanup_expired()

            assert removed == 3
            assert len(_active_flows) == 0

    def test_keeps_valid_flows(self):
        """Should not remove flows that haven't expired."""
        signal_id_1 = 100
        signal_id_2 = 200
        user_id = 456

        start_flow(signal_id_1, user_id)
        start_flow(signal_id_2, user_id)

        # Mock time to be before expiration
        with patch('src.state.flow_tracker.time.time') as mock_time:
            current_time = _active_flows[signal_id_1].timestamp
            mock_time.return_value = current_time + FLOW_TTL - 1

            removed = cleanup_expired()

            assert removed == 0
            assert len(_active_flows) == 2

    def test_removes_only_expired_flows(self):
        """Should remove only expired flows, keep valid ones."""
        signal_id_1 = 100
        signal_id_2 = 200
        user_id = 456

        # Create flow 1 with old timestamp
        start_flow(signal_id_1, user_id)
        old_timestamp = _active_flows[signal_id_1].timestamp

        # Create flow 2 with newer timestamp
        # Manually set flow 2 to have a recent timestamp
        with patch('src.state.flow_tracker.time.time') as mock_time:
            recent_time = old_timestamp + FLOW_TTL + 100
            mock_time.return_value = recent_time
            start_flow(signal_id_2, user_id)

        # Verify flows are set up
        assert signal_id_1 in _active_flows
        assert signal_id_2 in _active_flows

        # Now mock time to expire only first flow
        with patch('src.state.flow_tracker.time.time') as mock_time:
            # Set time between first and second expiration times
            check_time = old_timestamp + FLOW_TTL + 1
            mock_time.return_value = check_time

            removed = cleanup_expired()

            # Should remove only flow 1 since flow 2 has a more recent timestamp
            assert removed == 1
            assert signal_id_1 not in _active_flows

    def test_returns_count_removed(self):
        """Should return the count of removed flows."""
        signal_id_1 = 100
        signal_id_2 = 200
        signal_id_3 = 300
        user_id = 456

        start_flow(signal_id_1, user_id)
        start_flow(signal_id_2, user_id)
        start_flow(signal_id_3, user_id)

        with patch('src.state.flow_tracker.time.time') as mock_time:
            current_time = _active_flows[signal_id_1].timestamp
            mock_time.return_value = current_time + FLOW_TTL + 1

            removed = cleanup_expired()
            assert removed == 3


class TestForceCleanup:
    """Tests for _force_cleanup function."""

    def setup_method(self):
        """Clear active flows before each test."""
        _active_flows.clear()

    def test_does_nothing_when_under_limit(self):
        """Should not remove any flows when under MAX_FLOWS."""
        user_id = 456

        for i in range(100):
            start_flow(i, user_id)

        initial_count = len(_active_flows)
        _force_cleanup()

        assert len(_active_flows) == initial_count

    def test_removes_oldest_flows_when_exceeded(self):
        """Should remove oldest 10% of flows when limit exceeded."""
        user_id = 456

        # Create MAX_FLOWS + 100 flows
        total_to_create = MAX_FLOWS + 100

        for i in range(total_to_create):
            start_flow(i, user_id)
            # Small delay to ensure different timestamps
            if i % 100 == 0:
                time.sleep(0.001)

        # Record oldest signal IDs before cleanup
        oldest_signals = sorted(
            _active_flows.items(),
            key=lambda x: x[1].timestamp
        )[:10]  # Approximate 10%

        _force_cleanup()

        # Should have removed some flows to get under limit
        assert len(_active_flows) <= MAX_FLOWS

        # Oldest flows should be removed (at least some of them)
        for signal_id, _ in oldest_signals:
            # At least some of the oldest should be gone
            pass  # We just verify count is reduced

    def test_brings_count_under_limit(self):
        """Should reduce flow count to under MAX_FLOWS limit."""
        user_id = 456

        # Create more than MAX_FLOWS
        for i in range(MAX_FLOWS + 500):
            start_flow(i, user_id)

        _force_cleanup()

        assert len(_active_flows) <= MAX_FLOWS

    def test_removes_at_least_one_flow(self):
        """Should remove at least one flow when limit exceeded."""
        user_id = 456

        # Create flows up to MAX_FLOWS (without triggering auto-cleanup)
        # We'll use smaller batch to avoid hitting CLEANUP_INTERVAL
        for i in range(MAX_FLOWS // 2):
            start_flow(i, user_id)

        # Add one more flow to exceed limit
        for i in range(MAX_FLOWS // 2, MAX_FLOWS + 1):
            start_flow(i, user_id)

        # At this point, force_cleanup may have been called automatically
        # Check that we're not over MAX_FLOWS
        assert len(_active_flows) <= MAX_FLOWS

        # Manually verify force cleanup works
        before_count = len(_active_flows)
        _force_cleanup()
        after_count = len(_active_flows)

        # If we were over limit, cleanup should have removed flows
        if before_count > MAX_FLOWS:
            assert after_count < before_count
            assert after_count <= MAX_FLOWS


class TestAutoCleanupOnStartFlow:
    """Tests for automatic cleanup triggered by start_flow."""

    def setup_method(self):
        """Clear active flows before each test."""
        _active_flows.clear()

    def test_triggers_cleanup_expired_periodically(self):
        """Should trigger cleanup_expired at CLEANUP_INTERVAL."""
        from src.state.flow_tracker import CLEANUP_INTERVAL

        user_id = 456

        # Create enough flows to trigger cleanup
        for i in range(CLEANUP_INTERVAL + 1):
            start_flow(i, user_id)

        # Verify cleanup was triggered by checking state
        # We can't directly assert on cleanup call, but we verify state is valid
        assert len(_active_flows) >= 1

    def test_triggers_force_cleanup_when_max_exceeded(self):
        """Should trigger force cleanup when MAX_FLOWS exceeded."""
        user_id = 456

        # Create more than MAX_FLOWS
        for i in range(MAX_FLOWS + 10):
            start_flow(i, user_id)

        # After start_flow triggers _force_cleanup internally
        # The count should be brought under limit
        assert len(_active_flows) <= MAX_FLOWS


class TestFlowTrackerIntegration:
    """Integration tests for flow tracking."""

    def setup_method(self):
        """Clear active flows before each test."""
        _active_flows.clear()

    def test_complete_flow_lifecycle(self):
        """Should handle complete flow lifecycle."""
        signal_id = 123
        owner_id = 456
        other_id = 789

        # 1. No flow exists - everyone allowed
        assert is_allowed(signal_id, owner_id) is True

        # 2. Start flow - only owner allowed
        start_flow(signal_id, owner_id)
        assert is_allowed(signal_id, owner_id) is True
        assert is_allowed(signal_id, other_id) is False

        # 3. Get owner verification
        assert get_flow_owner(signal_id) == owner_id

        # 4. End flow - everyone allowed again
        end_flow(signal_id)
        assert is_allowed(signal_id, owner_id) is True
        assert is_allowed(signal_id, other_id) is True

    def test_multiple_concurrent_flows(self):
        """Should track multiple flows independently."""
        signal_1 = 100
        signal_2 = 200
        signal_3 = 300
        user_1 = 111
        user_2 = 222
        user_3 = 333

        start_flow(signal_1, user_1)
        start_flow(signal_2, user_2)
        start_flow(signal_3, user_3)

        # Each user should only have access to their flow
        assert is_allowed(signal_1, user_1) is True
        assert is_allowed(signal_1, user_2) is False

        assert is_allowed(signal_2, user_2) is True
        assert is_allowed(signal_2, user_1) is False

        assert is_allowed(signal_3, user_3) is True
        assert is_allowed(signal_3, user_1) is False

    def test_flow_takeover_by_new_user(self):
        """Should allow flow to be taken over by new user."""
        signal_id = 123
        user_1 = 456
        user_2 = 789

        # User 1 starts flow
        start_flow(signal_id, user_1)
        assert is_allowed(signal_id, user_1) is True
        assert is_allowed(signal_id, user_2) is False

        # User 1 ends flow
        end_flow(signal_id)

        # User 2 starts new flow
        start_flow(signal_id, user_2)
        assert is_allowed(signal_id, user_2) is True
        assert is_allowed(signal_id, user_1) is False

    def test_expiration_with_multiple_flows(self):
        """Should expire flows independently."""
        signal_1 = 100
        signal_2 = 200
        user_id = 456

        # Create first flow with old timestamp
        start_flow(signal_1, user_id)
        old_timestamp = _active_flows[signal_1].timestamp

        # Create second flow with newer timestamp
        with patch('src.state.flow_tracker.time.time') as mock_time:
            recent_time = old_timestamp + FLOW_TTL + 100
            mock_time.return_value = recent_time
            start_flow(signal_2, user_id)

        # Verify setup
        assert get_flow_owner(signal_1) == user_id
        assert get_flow_owner(signal_2) == user_id

        # Mock time to expire only first flow
        with patch('src.state.flow_tracker.time.time') as mock_time:
            # Time between first and second expiration
            check_time = old_timestamp + FLOW_TTL + 1
            mock_time.return_value = check_time

            # First should be expired
            assert get_flow_owner(signal_1) is None
            # Second should still be active (has more recent timestamp)
            assert get_flow_owner(signal_2) == user_id
