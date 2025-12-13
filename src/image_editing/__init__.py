"""Image editing module with multiple backends."""
from src.image_editing.base import ImageEditor, EditResult

__all__ = ["ImageEditor", "EditResult"]

# Conditional imports for editors - catch all exceptions, not just ImportError
try:
    from src.image_editing.paddleocr_editor import PaddleOCREditor
    __all__.append("PaddleOCREditor")
except Exception:
    pass

try:
    from src.image_editing.gemini_editor import GeminiImageEditor
    __all__.append("GeminiImageEditor")
except Exception:
    pass

try:
    from src.image_editing.openai_editor import OpenAIImageEditor
    __all__.append("OpenAIImageEditor")
except Exception:
    pass
