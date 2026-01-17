"""
Factory for creating image editor instances.

This module provides a factory pattern for instantiating image editors
based on configuration. Supports primary editor selection with fallback.
"""

from typing import Dict, Optional, Type

import structlog

from src.config import config
from src.image_editing.base import ImageEditor
from src.image_editing.gemini_editor import GeminiImageEditor
from src.image_editing.openai_editor import OpenAIImageEditor

logger = structlog.get_logger(__name__)


class ImageEditorFactory:
    """
    Factory for creating image editor instances.

    Provides centralized editor instantiation with support for:
    - Primary editor selection from config
    - Fallback editor if primary is unavailable
    - Availability checking before instantiation
    """

    # Registry of available editor implementations
    _editors: Dict[str, Type[ImageEditor]] = {
        "openai": OpenAIImageEditor,
        "gemini": GeminiImageEditor,
    }

    @classmethod
    def register(cls, name: str, editor_class: Type[ImageEditor]) -> None:
        """
        Register a new image editor.

        Args:
            name: Name identifier for the editor (e.g., 'openai', 'gemini')
            editor_class: Class that implements ImageEditor interface

        Example:
            >>> ImageEditorFactory.register('custom', CustomImageEditor)
        """
        cls._editors[name.lower()] = editor_class
        logger.info("Registered image editor", name=name.lower())

    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        Unregister an image editor.

        Args:
            name: Name of editor to remove

        Returns:
            True if editor was removed, False if not found
        """
        name_lower = name.lower()
        if name_lower in cls._editors:
            del cls._editors[name_lower]
            logger.info("Unregistered image editor", name=name_lower)
            return True
        return False

    @classmethod
    def get_editor(cls, name: Optional[str] = None) -> ImageEditor:
        """
        Get an image editor instance by name.

        Args:
            name: Name of the editor ("openai", "gemini").
                  If None, uses config.IMAGE_EDITOR.

        Returns:
            ImageEditor instance

        Raises:
            ValueError: If editor name is unknown
            RuntimeError: If editor is not available

        Examples:
            >>> editor = ImageEditorFactory.get_editor("openai")
            >>> editor = ImageEditorFactory.get_editor()  # Uses config
        """
        editor_name = (name or config.IMAGE_EDITOR).lower()

        logger.info("Requesting image editor", editor=editor_name, from_config=name is None)

        # Check if editor exists in registry
        if editor_name not in cls._editors:
            available = ", ".join(cls._editors.keys())
            error_msg = f"Unknown image editor: {editor_name}. Available: {available}"
            logger.error("Unknown editor requested", editor=editor_name, available=available)
            raise ValueError(error_msg)

        # Instantiate the editor
        editor_class = cls._editors[editor_name]
        editor = editor_class()

        # Check availability
        if not editor.is_available():
            error_msg = f"Editor '{editor_name}' is not available (missing dependencies or credentials)"
            logger.error(
                "Editor not available",
                editor=editor_name,
                reason="is_available() returned False"
            )
            raise RuntimeError(error_msg)

        logger.info("Image editor created successfully", editor=editor_name)
        return editor

    @classmethod
    def get_editor_with_fallback(cls) -> ImageEditor:
        """
        Get primary image editor with automatic fallback.

        Attempts to get the primary editor from config.IMAGE_EDITOR.
        If unavailable, falls back to config.IMAGE_EDITOR_FALLBACK.

        Returns:
            ImageEditor instance (primary or fallback)

        Raises:
            RuntimeError: If both primary and fallback editors are unavailable

        Examples:
            >>> editor = ImageEditorFactory.get_editor_with_fallback()
            >>> # Will use primary, or fallback if primary fails
        """
        primary_name = config.IMAGE_EDITOR.lower()
        fallback_name = (config.IMAGE_EDITOR_FALLBACK or "").lower()

        logger.info(
            "Getting editor with fallback",
            primary=primary_name,
            fallback=fallback_name or "none"
        )

        # Try primary editor
        try:
            editor = cls.get_editor(primary_name)
            logger.info("Using primary image editor", editor=primary_name)
            return editor
        except (ValueError, RuntimeError) as e:
            logger.warning(
                "Primary editor unavailable, trying fallback",
                primary=primary_name,
                error=str(e),
                fallback=fallback_name or "none"
            )

        # Try fallback editor if configured
        if not fallback_name:
            error_msg = (
                f"Primary editor '{primary_name}' unavailable and no fallback configured. "
                f"Set IMAGE_EDITOR_FALLBACK in config."
            )
            logger.error("No fallback editor configured", primary=primary_name)
            raise RuntimeError(error_msg)

        try:
            editor = cls.get_editor(fallback_name)
            logger.info(
                "Using fallback image editor",
                primary=primary_name,
                fallback=fallback_name
            )
            return editor
        except (ValueError, RuntimeError) as e:
            error_msg = (
                f"Both primary '{primary_name}' and fallback '{fallback_name}' "
                f"editors are unavailable: {e}"
            )
            logger.error(
                "All editors unavailable",
                primary=primary_name,
                fallback=fallback_name,
                error=str(e)
            )
            raise RuntimeError(error_msg)

    @classmethod
    def list_available_editors(cls) -> Dict[str, bool]:
        """
        List all registered editors and their availability status.

        Returns:
            Dictionary mapping editor names to availability (True/False)

        Examples:
            >>> status = ImageEditorFactory.list_available_editors()
            >>> # {'openai': True, 'gemini': False}
        """
        availability = {}

        for name, editor_class in cls._editors.items():
            try:
                editor = editor_class()
                availability[name] = editor.is_available()
            except Exception as e:
                logger.warning(
                    "Error checking editor availability",
                    editor=name,
                    error=str(e)
                )
                availability[name] = False

        logger.debug("Editor availability check", availability=availability)
        return availability
