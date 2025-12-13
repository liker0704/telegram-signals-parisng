"""
Vision provider factory with registry pattern and environment-based configuration.

This module provides a factory for creating and managing vision provider instances.
It supports:
- Registry pattern for extensible provider registration
- Lazy singleton instantiation for each provider
- Environment-based configuration via VISION_PROVIDER
- Thread-safe provider instance management
"""

import threading
from typing import Dict, Optional, Type

from src.config import config
from src.utils.logger import get_logger
from src.vision.base import VisionProvider, VisionProviderError

logger = get_logger(__name__)


class VisionProviderFactory:
    """
    Factory for creating and managing vision provider instances.

    This factory implements the registry pattern to allow dynamic provider
    registration and lazy singleton instantiation for efficient resource usage.

    Class Attributes:
        _providers: Registry mapping provider names to provider classes
        _instances: Cache of instantiated provider singletons
        _lock: Thread lock for safe instance creation
    """

    _providers: Dict[str, Type[VisionProvider]] = {}
    _instances: Dict[str, VisionProvider] = {}
    _lock = threading.Lock()

    @classmethod
    def register(cls, name: str, provider_class: Type[VisionProvider]) -> None:
        """
        Register a vision provider class in the factory.

        This method allows providers to be registered dynamically, enabling
        extensibility without modifying the factory code.

        Args:
            name: Provider name (e.g., "gemini", "openai", "anthropic")
            provider_class: Provider class that extends VisionProvider

        Raises:
            ValueError: If name is empty or provider_class is invalid
            VisionProviderError: If provider is already registered

        Example:
            >>> VisionProviderFactory.register("gemini", GeminiVisionProvider)
        """
        if not name:
            raise ValueError("Provider name cannot be empty")

        if not isinstance(provider_class, type) or not issubclass(provider_class, VisionProvider):
            raise ValueError(
                f"Provider class must be a subclass of VisionProvider, got {provider_class}"
            )

        if name in cls._providers:
            logger.warning(
                "Provider already registered, overwriting",
                provider_name=name,
                existing_class=cls._providers[name].__name__,
                new_class=provider_class.__name__
            )

        cls._providers[name] = provider_class
        logger.info(
            "Vision provider registered",
            provider_name=name,
            provider_class=provider_class.__name__
        )

    @classmethod
    def get_provider(cls, name: str) -> VisionProvider:
        """
        Get or create a vision provider instance by name.

        This method implements lazy singleton pattern - each provider is
        instantiated only once and cached for subsequent requests.
        Thread-safe using double-checked locking.

        Args:
            name: Provider name (e.g., "gemini", "openai", "anthropic")

        Returns:
            VisionProvider: Singleton instance of the requested provider

        Raises:
            VisionProviderError: If provider is not registered or instantiation fails

        Example:
            >>> provider = VisionProviderFactory.get_provider("gemini")
            >>> result = await provider.extract_text(image)
        """
        # Normalize provider name to lowercase
        name = name.lower().strip()

        if not name:
            raise VisionProviderError("Provider name cannot be empty")

        # Check if provider is registered
        if name not in cls._providers:
            available = ", ".join(cls._providers.keys()) if cls._providers else "none"
            raise VisionProviderError(
                f"Vision provider '{name}' is not registered. "
                f"Available providers: {available}"
            )

        # Check if instance already exists (fast path, no lock)
        if name in cls._instances:
            return cls._instances[name]

        # Create new instance with thread safety (slow path)
        with cls._lock:
            # Double-check after acquiring lock
            if name not in cls._instances:
                try:
                    logger.debug(
                        "Creating new provider instance",
                        provider_name=name
                    )
                    provider_class = cls._providers[name]
                    cls._instances[name] = provider_class()
                    logger.info(
                        "Provider instance created",
                        provider_name=name,
                        provider_class=provider_class.__name__
                    )
                except Exception as e:
                    logger.error(
                        "Failed to instantiate provider",
                        provider_name=name,
                        error=str(e)
                    )
                    raise VisionProviderError(
                        f"Failed to instantiate provider '{name}': {str(e)}"
                    ) from e

            return cls._instances[name]

    @classmethod
    def from_env_config(cls) -> VisionProvider:
        """
        Create provider from environment configuration.

        This method reads the VISION_PROVIDER environment variable and returns
        the corresponding provider instance. If VISION_PROVIDER is not set,
        defaults to "gemini".

        Returns:
            VisionProvider: Provider instance based on VISION_PROVIDER env var

        Raises:
            VisionProviderError: If configured provider is not available

        Example:
            >>> # VISION_PROVIDER=gemini in .env
            >>> provider = VisionProviderFactory.from_env_config()
            >>> assert provider.name == "gemini"
        """
        # Get provider name from config with default fallback
        provider_name = getattr(config, 'VISION_PROVIDER', 'gemini')

        logger.info(
            "Creating provider from environment config",
            provider_name=provider_name
        )

        try:
            provider = cls.get_provider(provider_name)

            # Check if provider is actually available (has required API keys)
            if not provider.is_available:
                logger.warning(
                    "Configured provider is not available (missing API keys)",
                    provider_name=provider_name
                )
                raise VisionProviderError(
                    f"Provider '{provider_name}' is configured but not available. "
                    f"Check if required API keys are set."
                )

            logger.info(
                "Provider created from environment config",
                provider_name=provider.name,
                is_available=provider.is_available
            )

            return provider

        except Exception as e:
            logger.error(
                "Failed to create provider from environment config",
                provider_name=provider_name,
                error=str(e)
            )
            raise

    @classmethod
    def list_providers(cls) -> Dict[str, str]:
        """
        List all registered providers with their class names.

        Returns:
            Dict[str, str]: Mapping of provider names to class names

        Example:
            >>> providers = VisionProviderFactory.list_providers()
            >>> print(providers)
            {'gemini': 'GeminiVisionProvider', 'openai': 'OpenAIVisionProvider'}
        """
        return {
            name: provider_class.__name__
            for name, provider_class in cls._providers.items()
        }

    @classmethod
    def clear_instances(cls) -> None:
        """
        Clear all cached provider instances.

        This method is primarily useful for testing or dynamic reconfiguration.
        After calling this, get_provider() will create fresh instances.

        Warning:
            This should not be used in production code as it may break
            existing references to provider instances.
        """
        with cls._lock:
            cls._instances.clear()
            logger.debug("All provider instances cleared")


# ============================================================================
# Auto-register built-in providers
# ============================================================================

# Import and register Gemini provider
try:
    from src.vision.providers.gemini import GeminiVisionProvider
    VisionProviderFactory.register("gemini", GeminiVisionProvider)
except ImportError as e:
    logger.warning(
        "Failed to import GeminiVisionProvider",
        error=str(e)
    )

# Import and register OpenAI provider
try:
    from src.vision.providers.openai import OpenAIVisionProvider
    VisionProviderFactory.register("openai", OpenAIVisionProvider)
except ImportError as e:
    logger.warning(
        "Failed to import OpenAIVisionProvider",
        error=str(e)
    )

# Import and register Anthropic provider
try:
    from src.vision.providers.anthropic import AnthropicVisionProvider
    VisionProviderFactory.register("anthropic", AnthropicVisionProvider)
except ImportError as e:
    logger.warning(
        "Failed to import AnthropicVisionProvider",
        error=str(e)
    )
