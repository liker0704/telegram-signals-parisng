"""
Gemini-based image editor.

This editor uses Google's Gemini API with gemini-2.5-flash-image model
to perform AI-powered image text editing by translating Russian to English.
"""

import asyncio
from pathlib import Path
from typing import Dict, Optional

import structlog
from PIL import Image

from src.image_editing.base import ImageEditor, EditResult
from src.utils.security import validate_image_file
from src.config import config

logger = structlog.get_logger(__name__)


class GeminiImageEditor(ImageEditor):
    """
    Image editor using Gemini AI for text translation and image editing.

    This editor sends the entire image to Gemini with a prompt to translate
    Russian text to English, and Gemini returns a modified image with the
    text replaced.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the Gemini image editor.

        Args:
            api_key: Google Gemini API key (defaults to config.GEMINI_API_KEY)
            model: Gemini model to use (defaults to config.GEMINI_IMAGE_MODEL)
        """
        self.api_key = api_key or config.GEMINI_API_KEY
        self.model = model or config.GEMINI_IMAGE_MODEL
        self._client = None
        logger.info("GeminiImageEditor initialized", model=self.model)

    @property
    def name(self) -> str:
        """Get the name of this editor."""
        return "gemini"

    def is_available(self) -> bool:
        """
        Check if Gemini editor is available.

        Returns:
            True if API key is configured, False otherwise
        """
        return bool(self.api_key)

    def _get_client(self):
        """Lazy-load the Gemini client."""
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info("Gemini client initialized")
            except ImportError as e:
                logger.error("Failed to import google.genai", error=str(e))
                raise RuntimeError("google-genai library not installed") from e
        return self._client

    def edit_image(
        self,
        image_path: str,
        translations: Dict[str, str],
        output_path: Optional[str] = None
    ) -> EditResult:
        """
        Edit image using Gemini AI.

        Args:
            image_path: Path to input image
            translations: Dict mapping original text to replacement text
                         (used to build the prompt)
            output_path: Optional path to save edited image

        Returns:
            EditResult with success status and edited image
        """
        try:
            if not self.is_available():
                logger.error("Gemini editor not available - API key missing")
                return EditResult(
                    success=False,
                    error="Gemini API key not configured",
                    method=self.name
                )

            # Validate image path
            if not validate_image_file(image_path):
                logger.error("Invalid or unsafe image path", path=image_path)
                return EditResult(
                    success=False,
                    error="Invalid or unsafe image path",
                    method=self.name
                )

            logger.info(
                "Gemini editing image",
                image_path=image_path,
                num_translations=len(translations),
                output_path=output_path,
                model=self.model
            )

            # Build prompt from translations
            prompt = self._build_prompt(translations)

            # Load image
            with open(image_path, "rb") as f:
                image_data = f.read()

            client = self._get_client()

            # Call Gemini API (synchronous)
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    prompt,
                    {"mime_type": "image/jpeg", "data": image_data}
                ]
            )

            # Extract image from response
            if not response.candidates or not response.candidates[0].content.parts:
                logger.error("Gemini returned empty response")
                return EditResult(
                    success=False,
                    error="Gemini returned empty response",
                    method=self.name
                )

            # Find the image part in the response
            image_part = None
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    image_part = part
                    break

            if not image_part:
                logger.error("No image found in Gemini response")
                return EditResult(
                    success=False,
                    error="No image in Gemini response",
                    method=self.name
                )

            # Convert bytes to PIL Image
            from io import BytesIO
            edited_image = Image.open(BytesIO(image_part.inline_data.data))

            # Save if output path specified
            if output_path:
                edited_image.save(output_path, quality=95)
                logger.info("Gemini edited image saved", path=output_path)

            logger.info("Gemini editing successful")
            return EditResult(
                success=True,
                edited_image=edited_image,
                method=self.name,
                metadata={
                    "input_path": image_path,
                    "output_path": output_path,
                    "model": self.model,
                    "num_translations": len(translations)
                }
            )

        except Exception as e:
            logger.error("Gemini editing error", error=str(e), exc_info=True)
            return EditResult(
                success=False,
                error=f"Gemini editing failed: {str(e)}",
                method=self.name
            )

    async def edit_image_async(
        self,
        image_path: str,
        translations: Dict[str, str],
        output_path: Optional[str] = None
    ) -> EditResult:
        """
        Async version of edit_image.

        Runs the synchronous operation in a thread pool to avoid blocking.

        Args:
            image_path: Path to input image
            translations: Dict mapping original text to replacement text
            output_path: Optional path to save edited image

        Returns:
            EditResult with success status and edited image
        """
        return await asyncio.to_thread(
            self.edit_image,
            image_path=image_path,
            translations=translations,
            output_path=output_path
        )

    def _build_prompt(self, translations: Dict[str, str]) -> str:
        """
        Build a prompt for Gemini based on the translations.

        Args:
            translations: Dict mapping original text to replacement text

        Returns:
            Prompt string for Gemini
        """
        if not translations:
            return (
                "Translate all Russian text in this image to English. "
                "Preserve the original formatting, colors, and layout. "
                "Return the edited image with English text."
            )

        # Build a prompt with specific translations
        replacements = "\n".join(
            f"- '{orig}' → '{trans}'"
            for orig, trans in translations.items()
        )

        return (
            f"Edit this image by replacing the following text:\n\n{replacements}\n\n"
            "Preserve the original formatting, colors, fonts, and layout exactly. "
            "Keep all other elements of the image unchanged. "
            "Return the edited image with the text replaced."
        )
