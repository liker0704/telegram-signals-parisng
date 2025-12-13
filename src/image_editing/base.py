"""
Base classes and interfaces for image editing.

This module defines the abstract base class for image editors
and the result dataclass for edit operations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional
from PIL import Image


@dataclass
class EditResult:
    """
    Result of an image editing operation.

    Attributes:
        success: Whether the edit operation succeeded
        edited_image: The edited PIL Image (None if failed)
        error: Error message if operation failed
        method: Name of the editing method/backend used
        metadata: Additional metadata about the operation
    """
    success: bool
    edited_image: Optional[Image.Image] = None
    error: Optional[str] = None
    method: str = "unknown"
    metadata: Optional[Dict] = None

    def __post_init__(self):
        """Ensure metadata is initialized."""
        if self.metadata is None:
            self.metadata = {}


class ImageEditor(ABC):
    """
    Abstract base class for image editors.

    All image editor implementations must extend this class
    and implement the required methods.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this editor is available for use.

        Returns:
            True if the editor can be used, False otherwise
        """
        pass

    @abstractmethod
    def edit_image(
        self,
        image_path: str,
        translations: Dict[str, str],
        output_path: Optional[str] = None
    ) -> EditResult:
        """
        Edit an image by replacing text according to translations.

        Args:
            image_path: Path to the input image file
            translations: Dictionary mapping original text to replacement text
            output_path: Optional path to save the edited image

        Returns:
            EditResult with success status and edited image (or error)
        """
        pass

    @abstractmethod
    async def edit_image_async(
        self,
        image_path: str,
        translations: Dict[str, str],
        output_path: Optional[str] = None
    ) -> EditResult:
        """
        Async version of edit_image.

        Args:
            image_path: Path to the input image file
            translations: Dictionary mapping original text to replacement text
            output_path: Optional path to save the edited image

        Returns:
            EditResult with success status and edited image (or error)
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the name of this editor.

        Returns:
            Human-readable name of the editor
        """
        pass
