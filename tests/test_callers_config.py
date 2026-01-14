"""Tests for CallersConfig singleton class."""

import re
import pytest
from src.callers_config import CallersConfig


class TestCallersConfigSingleton:
    """Tests for singleton pattern."""

    def setup_method(self):
        """Reset singleton before each test."""
        CallersConfig.reset()

    def test_get_instance_returns_instance(self):
        """Test that get_instance returns CallersConfig instance."""
        config = CallersConfig.get_instance()
        assert isinstance(config, CallersConfig)

    def test_singleton_same_instance(self):
        """Test that get_instance returns same instance on multiple calls."""
        c1 = CallersConfig.get_instance()
        c2 = CallersConfig.get_instance()
        assert c1 is c2

    def test_reset_creates_new_instance(self):
        """Test that reset() creates new instance."""
        c1 = CallersConfig.get_instance()
        CallersConfig.reset()
        c2 = CallersConfig.get_instance()
        assert c1 is not c2

    def test_reset_clears_instance(self):
        """Test that reset() sets _instance to None."""
        CallersConfig.get_instance()
        CallersConfig.reset()
        assert CallersConfig._instance is None


class TestIsKnownCaller:
    """Tests for is_known_caller method."""

    def setup_method(self):
        """Reset singleton before each test."""
        CallersConfig.reset()

    def test_known_caller_mark_tivan(self):
        """Test known caller Mark Tivan."""
        config = CallersConfig.get_instance()
        assert config.is_known_caller(1018248833) is True

    def test_known_caller_daniil(self):
        """Test known caller Daniil Nikolaev."""
        config = CallersConfig.get_instance()
        assert config.is_known_caller(1155161257) is True

    def test_known_caller_bendi(self):
        """Test known caller Bendi."""
        config = CallersConfig.get_instance()
        assert config.is_known_caller(468446980) is True

    def test_known_caller_kvaziroom(self):
        """Test known caller Kvaziroom."""
        config = CallersConfig.get_instance()
        assert config.is_known_caller(740952897) is True

    def test_known_caller_iskeib(self):
        """Test known caller Iskeib."""
        config = CallersConfig.get_instance()
        assert config.is_known_caller(5575681795) is True

    def test_unknown_caller(self):
        """Test unknown caller returns False."""
        config = CallersConfig.get_instance()
        assert config.is_known_caller(999999999) is False

    def test_unknown_caller_zero(self):
        """Test caller with ID 0."""
        config = CallersConfig.get_instance()
        assert config.is_known_caller(0) is False


class TestGetDetectionPatterns:
    """Tests for get_detection_patterns method."""

    def setup_method(self):
        """Reset singleton before each test."""
        CallersConfig.reset()

    def test_detection_patterns_known_caller_hashtag(self):
        """Test detection patterns for known caller with hashtag pattern."""
        config = CallersConfig.get_instance()
        patterns = config.get_detection_patterns(1018248833)

        assert isinstance(patterns, list)
        assert len(patterns) > 0
        assert all(isinstance(p, re.Pattern) for p in patterns)

    def test_detection_patterns_known_caller_bendi(self):
        """Test detection patterns for known caller with bendi pattern."""
        config = CallersConfig.get_instance()
        patterns = config.get_detection_patterns(468446980)

        assert isinstance(patterns, list)
        assert len(patterns) > 0
        assert all(isinstance(p, re.Pattern) for p in patterns)

    def test_detection_patterns_unknown_caller(self):
        """Test detection patterns for unknown caller (uses fallback)."""
        config = CallersConfig.get_instance()
        patterns = config.get_detection_patterns(999999999)

        assert isinstance(patterns, list)
        assert len(patterns) > 0
        assert all(isinstance(p, re.Pattern) for p in patterns)

    def test_detection_patterns_none_user_id(self):
        """Test detection patterns with None user_id (uses fallback)."""
        config = CallersConfig.get_instance()
        patterns = config.get_detection_patterns(None)

        assert isinstance(patterns, list)
        assert len(patterns) > 0
        assert all(isinstance(p, re.Pattern) for p in patterns)

    def test_detection_patterns_always_has_fallback(self):
        """Test that detection patterns never return empty list."""
        config = CallersConfig.get_instance()

        # Test various cases
        test_cases = [
            1018248833,  # known
            999999999,   # unknown
            None,        # None
        ]

        for user_id in test_cases:
            patterns = config.get_detection_patterns(user_id)
            assert len(patterns) > 0, f"No patterns for user_id={user_id}"


class TestGetExtractionPatterns:
    """Tests for get_extraction_patterns method."""

    def setup_method(self):
        """Reset singleton before each test."""
        CallersConfig.reset()

    def test_extraction_patterns_bendi(self):
        """Test extraction patterns for Bendi (468446980)."""
        config = CallersConfig.get_instance()
        extract = config.get_extraction_patterns(468446980)

        assert extract is not None
        assert isinstance(extract, dict)
        assert 'pair' in extract
        assert 'direction' in extract
        assert isinstance(extract['pair'], re.Pattern)
        assert isinstance(extract['direction'], re.Pattern)

    def test_extraction_patterns_mark_tivan(self):
        """Test extraction patterns for Mark Tivan (hashtag pattern returns None)."""
        config = CallersConfig.get_instance()
        extract = config.get_extraction_patterns(1018248833)

        # Hashtag pattern has no extraction
        assert extract is None

    def test_extraction_patterns_unknown_caller(self):
        """Test extraction patterns for unknown caller (uses fallback)."""
        config = CallersConfig.get_instance()
        extract = config.get_extraction_patterns(999999999)

        # Fallback includes bendi which has extraction
        # or returns None if fallback is hashtag only
        # Check config to see what fallback is
        assert extract is None or isinstance(extract, dict)

    def test_extraction_patterns_none_user_id(self):
        """Test extraction patterns with None user_id (uses fallback)."""
        config = CallersConfig.get_instance()
        extract = config.get_extraction_patterns(None)

        # Fallback may or may not have extraction patterns
        assert extract is None or isinstance(extract, dict)

    def test_extraction_patterns_kvaziroom(self):
        """Test extraction patterns for Kvaziroom (underscore pattern)."""
        config = CallersConfig.get_instance()
        extract = config.get_extraction_patterns(740952897)

        assert extract is not None
        assert isinstance(extract, dict)
        assert 'pair' in extract
        assert 'direction' in extract

    def test_extraction_patterns_iskeib(self):
        """Test extraction patterns for Iskeib (simple pattern)."""
        config = CallersConfig.get_instance()
        extract = config.get_extraction_patterns(5575681795)

        assert extract is not None
        assert isinstance(extract, dict)
        assert 'pair' in extract
        assert 'direction' in extract


class TestPatternMatching:
    """Tests for actual pattern matching behavior."""

    def setup_method(self):
        """Reset singleton before each test."""
        CallersConfig.reset()

    def test_hashtag_pattern_matches_idea(self):
        """Test hashtag pattern matches #Идея."""
        config = CallersConfig.get_instance()
        patterns = config.get_detection_patterns(1018248833)

        test_text = "#Идея BTC/USDT LONG"
        assert any(p.search(test_text) for p in patterns)

    def test_hashtag_pattern_matches_idea_english(self):
        """Test hashtag pattern matches #idea in English."""
        config = CallersConfig.get_instance()
        patterns = config.get_detection_patterns(1018248833)

        test_text = "#idea BTC/USDT LONG"
        assert any(p.search(test_text) for p in patterns)

    def test_hashtag_pattern_matches_idea_mixed(self):
        """Test hashtag pattern matches #Idea with mixed case."""
        config = CallersConfig.get_instance()
        patterns = config.get_detection_patterns(1018248833)

        test_text = "#Idea Some text"
        assert any(p.search(test_text) for p in patterns)

    def test_bendi_pattern_matches_long(self):
        """Test bendi pattern matches LONG signal."""
        config = CallersConfig.get_instance()
        patterns = config.get_detection_patterns(468446980)

        test_text = "**FF 🟢 LONG**"
        assert any(p.search(test_text) for p in patterns)

    def test_bendi_pattern_matches_short(self):
        """Test bendi pattern matches SHORT signal."""
        config = CallersConfig.get_instance()
        patterns = config.get_detection_patterns(468446980)

        test_text = "**BTC 🔴 SHORT**"
        assert any(p.search(test_text) for p in patterns)

    def test_bendi_extraction_pair(self):
        """Test bendi extraction pattern extracts pair."""
        config = CallersConfig.get_instance()
        extract = config.get_extraction_patterns(468446980)

        assert extract is not None
        test_text = "**BTC 🟢 LONG**"
        match = extract['pair'].search(test_text)
        assert match is not None

    def test_bendi_extraction_direction(self):
        """Test bendi extraction pattern extracts direction."""
        config = CallersConfig.get_instance()
        extract = config.get_extraction_patterns(468446980)

        assert extract is not None
        test_text = "**BTC 🟢 LONG**"
        match = extract['direction'].search(test_text)
        assert match is not None

    def test_underscore_pattern_matches(self):
        """Test underscore pattern matches format."""
        config = CallersConfig.get_instance()
        patterns = config.get_detection_patterns(740952897)

        test_text = "BTC_long"
        assert any(p.search(test_text) for p in patterns)

    def test_simple_pattern_matches(self):
        """Test simple pattern matches format."""
        config = CallersConfig.get_instance()
        patterns = config.get_detection_patterns(5575681795)

        test_text = "BTC LONG"
        assert any(p.search(test_text) for p in patterns)

    def test_hashtag_pattern_no_match_random_text(self):
        """Test hashtag pattern doesn't match random text."""
        config = CallersConfig.get_instance()
        patterns = config.get_detection_patterns(1018248833)

        test_text = "BTC LONG without hashtag"
        # Hashtag patterns should not match this
        # But we have fallback, so check if specific hashtag patterns match
        assert not any(p.search(test_text) for p in patterns
                      if p.pattern and '#' in p.pattern)


class TestConfigLoading:
    """Tests for config loading and initialization."""

    def setup_method(self):
        """Reset singleton before each test."""
        CallersConfig.reset()

    def test_config_loaded(self):
        """Test that config is loaded successfully."""
        config = CallersConfig.get_instance()
        assert config.config is not None
        assert len(config.config) > 0

    def test_callers_loaded(self):
        """Test that callers are loaded from config."""
        config = CallersConfig.get_instance()
        assert config.callers is not None
        assert len(config.callers) > 0
        assert 1018248833 in config.callers
        assert 468446980 in config.callers

    def test_patterns_loaded(self):
        """Test that patterns are loaded from config."""
        config = CallersConfig.get_instance()
        assert config.patterns is not None
        assert len(config.patterns) > 0

    def test_patterns_compiled(self):
        """Test that patterns are compiled (detect_compiled exists)."""
        config = CallersConfig.get_instance()
        for pattern_name, pattern_def in config.patterns.items():
            assert 'detect_compiled' in pattern_def
            assert isinstance(pattern_def['detect_compiled'], list)

    def test_fallback_config_structure(self):
        """Test fallback configuration structure."""
        config = CallersConfig.get_instance()
        fallback = config.config.get('fallback', {})
        assert fallback is not None
        # Should have either 'pattern' or 'patterns'
        assert 'pattern' in fallback or 'patterns' in fallback

    def test_pattern_flag_compilation(self):
        """Test that regex flags are properly compiled."""
        config = CallersConfig.get_instance()

        # Hashtag pattern should have IGNORECASE flag
        hashtag_pattern = config.patterns.get('hashtag', {})
        assert 'detect_compiled' in hashtag_pattern
        assert len(hashtag_pattern['detect_compiled']) > 0

        # Test that IGNORECASE is actually applied
        pattern = hashtag_pattern['detect_compiled'][0]
        assert pattern.search("#идея")
        assert pattern.search("#ИДЕЯ")
        assert pattern.search("#Идея")

    def test_multiline_flag_compilation(self):
        """Test that MULTILINE flag is applied."""
        config = CallersConfig.get_instance()

        # Underscore pattern should have MULTILINE flag
        underscore_pattern = config.patterns.get('underscore', {})
        assert 'detect_compiled' in underscore_pattern
        pattern = underscore_pattern['detect_compiled'][0]

        # Test multiline support
        test_text = "some text\nBTC_LONG\nmore text"
        assert pattern.search(test_text)


class TestGetPatternNames:
    """Tests for internal _get_pattern_names method."""

    def setup_method(self):
        """Reset singleton before each test."""
        CallersConfig.reset()

    def test_get_pattern_names_known_caller(self):
        """Test _get_pattern_names for known caller."""
        config = CallersConfig.get_instance()
        pattern_names = config._get_pattern_names(1018248833)

        assert isinstance(pattern_names, list)
        assert len(pattern_names) > 0
        assert 'hashtag' in pattern_names

    def test_get_pattern_names_bendi(self):
        """Test _get_pattern_names for Bendi."""
        config = CallersConfig.get_instance()
        pattern_names = config._get_pattern_names(468446980)

        assert isinstance(pattern_names, list)
        assert 'bendi' in pattern_names

    def test_get_pattern_names_unknown_caller(self):
        """Test _get_pattern_names for unknown caller uses fallback."""
        config = CallersConfig.get_instance()
        pattern_names = config._get_pattern_names(999999999)

        assert isinstance(pattern_names, list)
        assert len(pattern_names) > 0
        # Should use fallback patterns

    def test_get_pattern_names_none_user_id(self):
        """Test _get_pattern_names with None uses fallback."""
        config = CallersConfig.get_instance()
        pattern_names = config._get_pattern_names(None)

        assert isinstance(pattern_names, list)
        assert len(pattern_names) > 0


class TestFallbackBehavior:
    """Tests for fallback pattern behavior."""

    def setup_method(self):
        """Reset singleton before each test."""
        CallersConfig.reset()

    def test_fallback_detection_exists(self):
        """Test that FALLBACK_DETECTION pattern exists."""
        assert CallersConfig.FALLBACK_DETECTION is not None
        assert isinstance(CallersConfig.FALLBACK_DETECTION, re.Pattern)

    def test_fallback_detection_matches_hashtag(self):
        """Test that fallback pattern matches hashtag."""
        text = "#Идея BTC LONG"
        assert CallersConfig.FALLBACK_DETECTION.search(text)

    def test_fallback_detection_case_insensitive(self):
        """Test that fallback pattern is case insensitive."""
        assert CallersConfig.FALLBACK_DETECTION.search("#ИДЕЯ")
        assert CallersConfig.FALLBACK_DETECTION.search("#идея")
        assert CallersConfig.FALLBACK_DETECTION.search("#Идея")
        assert CallersConfig.FALLBACK_DETECTION.search("#IDEA")
        assert CallersConfig.FALLBACK_DETECTION.search("#idea")


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def setup_method(self):
        """Reset singleton before each test."""
        CallersConfig.reset()

    def test_negative_user_id(self):
        """Test with negative user ID."""
        config = CallersConfig.get_instance()
        assert config.is_known_caller(-1) is False
        patterns = config.get_detection_patterns(-1)
        assert len(patterns) > 0

    def test_large_user_id(self):
        """Test with very large user ID."""
        config = CallersConfig.get_instance()
        large_id = 999999999999999
        assert config.is_known_caller(large_id) is False
        patterns = config.get_detection_patterns(large_id)
        assert len(patterns) > 0

    def test_zero_user_id(self):
        """Test with user ID 0."""
        config = CallersConfig.get_instance()
        assert config.is_known_caller(0) is False
        patterns = config.get_detection_patterns(0)
        assert len(patterns) > 0

    def test_multiple_resets(self):
        """Test multiple sequential resets."""
        c1 = CallersConfig.get_instance()
        CallersConfig.reset()
        c2 = CallersConfig.get_instance()
        CallersConfig.reset()
        c3 = CallersConfig.get_instance()

        assert c1 is not c2
        assert c2 is not c3
        assert c1 is not c3
