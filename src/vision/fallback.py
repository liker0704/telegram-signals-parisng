"""
FallbackChain - Orchestrates fallback between multiple vision providers.
"""
import asyncio
from typing import List, Optional
from PIL import Image

from src.vision.base import VisionProvider, VisionResult, VisionProviderError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FallbackChain:
    """Orchestrates fallback between multiple vision providers."""

    def __init__(
        self,
        providers: List[VisionProvider],
        timeout_sec: float = 30.0,
        max_retries: int = 1
    ):
        """
        Initialize FallbackChain.

        Args:
            providers: List of vision providers to try in order
            timeout_sec: Timeout for each provider attempt
            max_retries: Max retries per provider before trying next
        """
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries

        # Filter to only available providers
        self._providers = [p for p in providers if p.is_available]

        if not self._providers:
            raise ValueError("No available providers in fallback chain")

        logger.info(
            "FallbackChain initialized",
            providers=[p.name for p in self._providers],
            timeout_sec=timeout_sec,
            max_retries=max_retries
        )

    @property
    def available_providers(self) -> List[str]:
        """Return names of available providers."""
        return [p.name for p in self._providers]

    async def extract_text(
        self,
        image: Image.Image,
        prompt: Optional[str] = None
    ) -> VisionResult:
        """
        Try providers in order until one succeeds.

        Args:
            image: PIL Image to process
            prompt: Optional custom prompt

        Returns:
            VisionResult from first successful provider

        Raises:
            VisionProviderError: If all providers fail
        """
        last_error: Optional[Exception] = None

        for provider in self._providers:
            for attempt in range(self.max_retries + 1):
                try:
                    logger.info(
                        "Trying vision provider",
                        provider=provider.name,
                        attempt=attempt + 1,
                        max_retries=self.max_retries + 1
                    )

                    result = await asyncio.wait_for(
                        provider.extract_text(image, prompt),
                        timeout=self.timeout_sec
                    )

                    logger.info(
                        "Vision extraction successful",
                        provider=provider.name,
                        extractions=len(result.extractions),
                        latency_ms=result.latency_ms
                    )

                    return result

                except asyncio.TimeoutError:
                    logger.warning(
                        "Vision provider timeout",
                        provider=provider.name,
                        attempt=attempt + 1,
                        timeout_sec=self.timeout_sec
                    )
                    last_error = TimeoutError(f"{provider.name} timed out after {self.timeout_sec}s")

                except Exception as e:
                    logger.warning(
                        "Vision provider failed",
                        provider=provider.name,
                        attempt=attempt + 1,
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    last_error = e

        # All providers failed
        logger.error(
            "All vision providers failed",
            providers=self.available_providers,
            last_error=str(last_error)
        )

        raise VisionProviderError(
            f"All providers failed. Last error: {last_error}",
            provider="fallback_chain"
        )
