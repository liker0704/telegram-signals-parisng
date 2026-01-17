"""
OpenAI-based image editor.

This editor uses OpenAI's image editing API (gpt-image-1 model)
to perform AI-powered image text editing.
"""

import asyncio
from pathlib import Path
from typing import Dict, Optional

import structlog
from PIL import Image

from src.config import config
from src.image_editing.base import EditResult, ImageEditor
from src.utils.security import validate_image_file

logger = structlog.get_logger(__name__)


class OpenAIImageEditor(ImageEditor):
    """
    Image editor using OpenAI's image editing API.

    This editor uses the images.edit() endpoint with a mask to replace
    text in images. It creates a mask from the image and uses a prompt
    to guide the text replacement.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the OpenAI image editor.

        Args:
            api_key: OpenAI API key (defaults to config.OPENAI_API_KEY)
            model: OpenAI model to use (defaults to config.OPENAI_IMAGE_MODEL)
        """
        self.api_key = api_key or (config.OPENAI_API_KEY or "")
        self.model = model or config.OPENAI_IMAGE_MODEL
        self._client = None
        logger.info("OpenAIImageEditor initialized", model=self.model)

    @property
    def name(self) -> str:
        """Get the name of this editor."""
        return "openai"

    def is_available(self) -> bool:
        """
        Check if OpenAI editor is available.

        Returns:
            True if API key is configured, False otherwise
        """
        return bool(self.api_key)

    def _get_client(self):
        """Lazy-load the OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
                logger.info("OpenAI client initialized")
            except ImportError as e:
                logger.error("Failed to import openai", error=str(e))
                raise RuntimeError("openai library not installed") from e
        return self._client

    # Supported sizes by OpenAI Images Edit API
    SUPPORTED_SIZES = {
        "1024x1024": 1.0,      # square
        "1536x1024": 1.5,      # landscape
        "1024x1536": 0.667,    # portrait
    }

    def _get_output_size(self, image_path: str) -> str:
        """
        Choose the best supported output size based on input image aspect ratio.

        OpenAI Images Edit API supports only:
        - 1024x1024 (square, 1:1)
        - 1536x1024 (landscape, 3:2)
        - 1024x1536 (portrait, 2:3)

        Uses threshold-based selection to avoid cropping:
        - Landscape (width > height * 1.1) → 1536x1024
        - Portrait (height > width * 1.1) → 1024x1536
        - Near-square → 1024x1024
        """
        with Image.open(image_path) as img:
            width, height = img.size
            aspect_ratio = width / height

        # Use thresholds to preserve orientation
        if width > height * 1.1:
            # Landscape image - use landscape output
            best_size = "1536x1024"
        elif height > width * 1.1:
            # Portrait image - use portrait output
            best_size = "1024x1536"
        else:
            # Near-square - use square
            best_size = "1024x1024"

        logger.debug(
            "Selected output size",
            input_size=f"{width}x{height}",
            aspect_ratio=round(aspect_ratio, 3),
            output_size=best_size
        )

        return best_size

    def edit_image(
        self,
        image_path: str,
        translations: Dict[str, str],
        output_path: Optional[str] = None
    ) -> EditResult:
        """
        Edit image using OpenAI's image editing API.

        Args:
            image_path: Path to input image
            translations: Dict mapping original text to replacement text
            output_path: Optional path to save edited image

        Returns:
            EditResult with success status and edited image
        """
        # Initialize mask_path before try block
        mask_path = None

        try:
            if not self.is_available():
                logger.error("OpenAI editor not available - API key missing")
                return EditResult(
                    success=False,
                    error="OpenAI API key not configured",
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
                "OpenAI editing image",
                image_path=image_path,
                num_translations=len(translations),
                output_path=output_path,
                model=self.model
            )

            # Build prompt from translations
            prompt = self._build_prompt(translations)

            # Choose output size based on input aspect ratio
            output_size = self._get_output_size(image_path)

            # Create mask for text regions (simple approach: white mask)
            # OpenAI uses the mask to determine which areas to edit
            mask_path = self._create_mask(image_path)

            try:
                client = self._get_client()

                # Open image and mask files
                with open(image_path, "rb") as image_file, open(mask_path, "rb") as mask_file:
                    # Call OpenAI image edit API
                    response = client.images.edit(
                        model=self.model,
                        image=image_file,
                        mask=mask_file,
                        prompt=prompt,
                        n=1,
                        size=output_size
                    )

                if not response.data:
                    logger.error("OpenAI returned empty response")
                    return EditResult(
                        success=False,
                        error="OpenAI returned empty response",
                        method=self.name
                    )

                # Get the edited image (supports both URL and base64 response)
                import base64
                from io import BytesIO

                image_data = response.data[0]

                if image_data.b64_json:
                    # New API returns base64 encoded image
                    image_bytes = base64.b64decode(image_data.b64_json)
                    edited_image = Image.open(BytesIO(image_bytes))
                elif image_data.url:
                    # Legacy API returns URL
                    import requests
                    image_response = requests.get(image_data.url)
                    image_response.raise_for_status()
                    edited_image = Image.open(BytesIO(image_response.content))
                else:
                    logger.error("OpenAI response has neither URL nor b64_json")
                    return EditResult(
                        success=False,
                        error="OpenAI response has no image data",
                        method=self.name
                    )

                # Save if output path specified
                if output_path:
                    edited_image.save(output_path, quality=95)
                    logger.info("OpenAI edited image saved", path=output_path)

                logger.info("OpenAI editing successful")
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

            finally:
                # Clean up temporary mask file
                if mask_path and Path(mask_path).exists():
                    Path(mask_path).unlink()

        except Exception as e:
            logger.error("OpenAI editing error", error=str(e), exc_info=True)
            return EditResult(
                success=False,
                error=f"OpenAI editing failed: {str(e)}",
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
        Build a detailed prompt for OpenAI based on the translations.

        Args:
            translations: Dict mapping original text to replacement text

        Returns:
            Detailed prompt string for OpenAI with explicit preservation instructions
        """
        if not translations:
            return (
                "Translate all Russian text in this image to English. "
                "Preserve the original formatting, colors, and layout exactly."
            )

        # Build bullet list of replacements
        replacements_list = "\n".join(
            f'- "{orig}" → "{trans}"'
            for orig, trans in translations.items()
        )

        return f"""This is a trading signal image. Replace the following text:

{replacements_list}

PRESERVE (keep exactly as is):
- Font style, size, weight, and color of all text
- Text position, alignment, and spacing
- All charts, candlesticks, and technical indicators
- Price scale, axis labels, and grid lines on the right side
- All other text elements not listed for replacement
- Background colors and overall composition
- Image dimensions and aspect ratio
- Border lines, boxes, and decorative elements

DO NOT:
- Add any watermarks, logos, or signatures
- Crop, resize, or change image dimensions
- Modify charts, indicators, or graphical elements
- Change colors, fonts, or styling
- Alter any text not explicitly listed for replacement
- Add or remove any visual elements

Replace ONLY the specified text while maintaining perfect visual consistency with the original image."""

    def _create_mask(self, image_path: str) -> str:
        """
        Create a mask for the image.

        For simplicity, creates a white mask (edit entire image).
        A more sophisticated approach would detect text regions.

        Args:
            image_path: Path to the input image

        Returns:
            Path to the created mask file
        """
        try:
            # Load original image
            with Image.open(image_path) as img:
                # Convert to RGBA
                img_rgba = img.convert("RGBA")

                # Create a white mask (fully opaque)
                # OpenAI uses transparent areas as the edit region
                mask = Image.new("RGBA", img_rgba.size, (255, 255, 255, 255))

                # Save mask to temporary file
                mask_path = str(Path(image_path).parent / f"{Path(image_path).stem}_mask.png")
                mask.save(mask_path)

                logger.debug("Created mask for OpenAI", mask_path=mask_path)
                return mask_path

        except Exception as e:
            logger.error("Failed to create mask", error=str(e))
            raise
