"""
Callers Configuration Loader
Singleton class to load and manage YAML config for signal callers.
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, Dict, List

import yaml

logger = logging.getLogger(__name__)


class CallersConfig:
    """
    Singleton configuration loader for signal caller patterns.

    Manages detection and extraction patterns for different signal callers.
    Loads configuration from config/callers.yaml with fallback to hashtag pattern.
    """

    _instance: Optional['CallersConfig'] = None

    # Flag mapping for regex compilation
    FLAG_MAP = {
        'IGNORECASE': re.IGNORECASE,
        'MULTILINE': re.MULTILINE,
        'DOTALL': re.DOTALL,
    }

    # Hardcoded fallback hashtag pattern
    FALLBACK_DETECTION = re.compile(
        r'#[ИиIi]де[яЯа]|#[Ii]dea',
        re.IGNORECASE
    )

    def __init__(self):
        """Initialize config loader and load patterns from YAML."""
        self.config: Dict = {}
        self.callers: Dict[int, Dict] = {}
        self.patterns: Dict[str, Dict] = {}
        self._load_config()

    @classmethod
    def get_instance(cls) -> 'CallersConfig':
        """
        Get singleton instance of CallersConfig.

        Returns:
            Singleton instance of CallersConfig
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """
        Reset singleton instance (for testing).
        """
        cls._instance = None

    def _get_config_path(self) -> Path:
        """Get absolute path to config/callers.yaml."""
        # Assume we're in src/ directory, go up to project root
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent
        return project_root / 'config' / 'callers.yaml'

    def _load_config(self) -> None:
        """
        Load configuration from YAML file.
        Falls back to hashtag pattern if file is missing or invalid.
        """
        config_path = self._get_config_path()

        if not config_path.exists():
            logger.warning(
                f"Config file not found: {config_path}. "
                "Using fallback hashtag pattern."
            )
            self._use_fallback()
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)

            # Extract callers and patterns sections
            self.callers = self.config.get('callers', {})
            self.patterns = self.config.get('patterns', {})

            # Compile all patterns
            self._compile_patterns()

            logger.info(
                f"Loaded config: {len(self.callers)} callers, "
                f"{len(self.patterns)} patterns"
            )

        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            self._use_fallback()

    def _use_fallback(self) -> None:
        """Use hardcoded fallback hashtag pattern."""
        self.patterns = {
            'hashtag': {
                'detect_compiled': [self.FALLBACK_DETECTION],
                'extract_compiled': None,
            }
        }
        self.config = {
            'fallback': {'pattern': 'hashtag'}
        }

    def _parse_flags(self, flags_str: Optional[str]) -> int:
        """
        Parse flag string like 'IGNORECASE|MULTILINE' to int flags.

        Args:
            flags_str: String like 'IGNORECASE|MULTILINE' or None

        Returns:
            Combined int flags for re.compile()
        """
        if not flags_str:
            return 0

        combined_flags = 0
        for flag_name in flags_str.split('|'):
            flag_name = flag_name.strip()
            if flag_name in self.FLAG_MAP:
                combined_flags |= self.FLAG_MAP[flag_name]
            else:
                logger.warning(f"Unknown regex flag: {flag_name}")

        return combined_flags

    def _compile_patterns(self) -> None:
        """
        Compile all regex patterns in the config.
        Invalid patterns are logged and skipped.
        """
        for pattern_name, pattern_def in self.patterns.items():
            try:
                # Compile detection pattern
                detect_regex = pattern_def.get('detect', '')
                flags = self._parse_flags(pattern_def.get('flags', ''))

                if not detect_regex:
                    logger.warning(
                        f"Pattern '{pattern_name}' has no detect regex, skipping"
                    )
                    continue

                pattern_def['detect_compiled'] = [
                    re.compile(detect_regex, flags)
                ]

                # Compile extraction patterns if present
                extract_def = pattern_def.get('extract')
                if extract_def:
                    extract_compiled = {}
                    for key, regex in extract_def.items():
                        extract_compiled[key] = re.compile(regex, flags)
                    pattern_def['extract_compiled'] = extract_compiled
                else:
                    pattern_def['extract_compiled'] = None

            except re.error as e:
                logger.error(
                    f"Failed to compile pattern '{pattern_name}': {e}"
                )
                # Remove invalid pattern
                pattern_def['detect_compiled'] = []
                pattern_def['extract_compiled'] = None

    def get_detection_patterns(self, user_id: Optional[int]) -> List[re.Pattern]:
        """
        Get compiled detection patterns for a user.

        Args:
            user_id: Telegram user ID, or None for fallback

        Returns:
            List of compiled regex patterns for signal detection
        """
        pattern_names = self._get_pattern_names(user_id)
        result = []
        for pattern_name in pattern_names:
            pattern_def = self.patterns.get(pattern_name, {})
            result.extend(pattern_def.get('detect_compiled', []))
        return result if result else [self.FALLBACK_DETECTION]

    def get_extraction_patterns(
        self, user_id: Optional[int]
    ) -> Optional[Dict[str, re.Pattern]]:
        """
        Get compiled extraction patterns for a user.

        Args:
            user_id: Telegram user ID, or None for fallback

        Returns:
            Dict with keys like 'pair', 'direction' mapped to compiled regex,
            or None if no extraction patterns defined
        """
        pattern_names = self._get_pattern_names(user_id)
        # Return first pattern's extraction that has one
        for pattern_name in pattern_names:
            pattern_def = self.patterns.get(pattern_name, {})
            extract = pattern_def.get('extract_compiled')
            if extract:
                return extract
        return None

    def is_known_caller(self, user_id: int) -> bool:
        """
        Check if user_id is a known caller in config.

        Args:
            user_id: Telegram user ID

        Returns:
            True if user_id is in callers config, False otherwise
        """
        return user_id in self.callers

    def _get_pattern_names(self, user_id: Optional[int]) -> List[str]:
        """
        Get pattern names for a user, or fallback patterns.

        Args:
            user_id: Telegram user ID or None

        Returns:
            List of pattern name strings (e.g., ['hashtag'], ['hashtag', 'bendi'])
        """
        if user_id and user_id in self.callers:
            pattern = self.callers[user_id].get('pattern', 'hashtag')
            return [pattern] if isinstance(pattern, str) else pattern

        # Use fallback patterns
        fallback = self.config.get('fallback', {})
        # Support both 'pattern' (single) and 'patterns' (list)
        if 'patterns' in fallback:
            return fallback['patterns']
        return [fallback.get('pattern', 'hashtag')]
