"""Vision provider implementations for the telegram-signals-parsing project."""

# Import providers conditionally to avoid dependency errors
__all__ = []

try:
    from src.vision.providers.gemini import GeminiVisionProvider
    __all__.append('GeminiVisionProvider')
except ImportError:
    pass

try:
    from src.vision.providers.openai import OpenAIVisionProvider
    __all__.append('OpenAIVisionProvider')
except ImportError:
    pass

try:
    from src.vision.providers.anthropic import AnthropicVisionProvider
    __all__.append('AnthropicVisionProvider')
except ImportError:
    pass
