"""
Integration tests for OpenAI translator and image editing.

Tests:
1. Syntax check for all modified files
2. Direct module imports (avoiding circular dependencies)
3. OpenAI translator tests
4. Configuration tests
5. Basic functionality verification
"""

import pytest
import sys
import os
import importlib
from unittest.mock import Mock, patch, MagicMock
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestSyntaxCheck:
    """Test syntax validation of modified files."""

    def test_openai_translator_syntax(self):
        """Verify openai.py has valid Python syntax."""
        import py_compile
        filepath = os.path.join(os.path.dirname(__file__), '..', 'src', 'translators', 'openai.py')
        try:
            py_compile.compile(filepath, doraise=True)
            assert True
        except py_compile.PyCompileError as e:
            pytest.fail(f"Syntax error in openai.py: {e}")

    def test_fallback_translator_syntax(self):
        """Verify fallback.py has valid Python syntax."""
        import py_compile
        filepath = os.path.join(os.path.dirname(__file__), '..', 'src', 'translators', 'fallback.py')
        try:
            py_compile.compile(filepath, doraise=True)
            assert True
        except py_compile.PyCompileError as e:
            pytest.fail(f"Syntax error in fallback.py: {e}")

    def test_translators_init_syntax(self):
        """Verify __init__.py has valid Python syntax."""
        import py_compile
        filepath = os.path.join(os.path.dirname(__file__), '..', 'src', 'translators', '__init__.py')
        try:
            py_compile.compile(filepath, doraise=True)
            assert True
        except py_compile.PyCompileError as e:
            pytest.fail(f"Syntax error in translators/__init__.py: {e}")

    def test_image_editor_factory_syntax(self):
        """Verify image editing factory has valid Python syntax."""
        import py_compile
        filepath = os.path.join(os.path.dirname(__file__), '..', 'src', 'image_editing', 'factory.py')
        try:
            py_compile.compile(filepath, doraise=True)
            assert True
        except py_compile.PyCompileError as e:
            pytest.fail(f"Syntax error in image_editing/factory.py: {e}")

    def test_image_editor_sync_syntax(self):
        """Verify image_editor.py has valid Python syntax."""
        import py_compile
        filepath = os.path.join(os.path.dirname(__file__), '..', 'src', 'ocr', 'image_editor.py')
        try:
            py_compile.compile(filepath, doraise=True)
            assert True
        except py_compile.PyCompileError as e:
            pytest.fail(f"Syntax error in ocr/image_editor.py: {e}")


class TestDirectImports:
    """Test direct module imports without circular dependencies."""

    def test_import_openai_module_directly(self):
        """Test importing openai module directly."""
        try:
            from src.translators import openai
            assert hasattr(openai, 'openai_translate'), "Should have openai_translate function"
            assert hasattr(openai, 'get_client'), "Should have get_client function"
            print("Successfully imported src.translators.openai")
        except ImportError as e:
            pytest.fail(f"Failed to import openai module: {e}")

    def test_import_fallback_module_directly(self):
        """Test importing fallback module directly."""
        try:
            from src.translators import fallback
            assert hasattr(fallback, 'translate_text_with_fallback'), "Should have translate_text_with_fallback function"
            print("Successfully imported src.translators.fallback")
        except ImportError as e:
            pytest.fail(f"Failed to import fallback module: {e}")

    def test_import_edit_image_text(self):
        """Test importing edit_image_text from ocr.image_editor."""
        try:
            from src.ocr import image_editor
            assert hasattr(image_editor, 'edit_image_text'), "Should have edit_image_text function"
            assert hasattr(image_editor, 'edit_image_text_sync'), "Should have edit_image_text_sync function"
            print("Successfully imported src.ocr.image_editor")
        except ImportError as e:
            pytest.fail(f"Failed to import image_editor: {e}")


class TestConfig:
    """Test configuration loading."""

    def test_config_import(self):
        """Test that config can be imported."""
        try:
            from src.config import config
            assert config is not None, "Config should be importable"
        except ImportError as e:
            pytest.fail(f"Failed to import config: {e}")

    def test_config_vision_provider(self):
        """Test that VISION_PROVIDER is configured."""
        from src.config import config
        assert hasattr(config, 'VISION_PROVIDER'), "Config should have VISION_PROVIDER"
        assert config.VISION_PROVIDER in ['gemini', 'openai', 'anthropic'], \
            f"VISION_PROVIDER should be gemini, openai, or anthropic, got {config.VISION_PROVIDER}"
        print(f"VISION_PROVIDER: {config.VISION_PROVIDER}")
        assert True

    def test_config_image_editor(self):
        """Test that IMAGE_EDITOR is configured."""
        from src.config import config
        assert hasattr(config, 'IMAGE_EDITOR'), "Config should have IMAGE_EDITOR"
        assert config.IMAGE_EDITOR in ['openai', 'gemini', 'paddleocr'], \
            f"IMAGE_EDITOR should be openai, gemini, or paddleocr, got {config.IMAGE_EDITOR}"
        print(f"IMAGE_EDITOR: {config.IMAGE_EDITOR}")
        assert True

    def test_config_openai_api_key(self):
        """Test that OPENAI_API_KEY is set if configured."""
        from src.config import config
        assert hasattr(config, 'OPENAI_API_KEY'), "Config should have OPENAI_API_KEY"
        if config.OPENAI_API_KEY:
            print(f"OPENAI_API_KEY is set (length: {len(config.OPENAI_API_KEY)})")
        else:
            print("OPENAI_API_KEY is not set")
        assert True

    def test_config_gemini_api_key(self):
        """Test that GEMINI_API_KEY is configured."""
        from src.config import config
        assert hasattr(config, 'GEMINI_API_KEY'), "Config should have GEMINI_API_KEY"
        assert config.GEMINI_API_KEY, "GEMINI_API_KEY should be set"
        print(f"GEMINI_API_KEY is set (length: {len(config.GEMINI_API_KEY)})")

    def test_config_vision_fallback_list(self):
        """Test vision fallback provider parsing."""
        from src.config import config
        fallback_list = config.vision_fallback_list
        assert isinstance(fallback_list, list), "vision_fallback_list should return a list"
        print(f"Vision fallback providers: {fallback_list}")


class TestOpenAIModule:
    """Test OpenAI module functions."""

    def test_openai_get_client_no_key(self):
        """Test get_client returns None when API key is not configured."""
        # Import and patch at module level
        from src.translators import openai as openai_module

        # Save original config
        original_key = openai_module.config.OPENAI_API_KEY

        try:
            # Temporarily set OPENAI_API_KEY to None
            openai_module.config.OPENAI_API_KEY = None

            # Reset global client
            openai_module._client = None

            client = openai_module.get_client()
            assert client is None, "Should return None when API key is not configured"
            print("get_client correctly returns None when API key is not set")
        finally:
            # Restore original
            openai_module.config.OPENAI_API_KEY = original_key

    def test_openai_translate_empty_text(self):
        """Test openai_translate returns input for empty text."""
        from src.translators.openai import openai_translate

        result = openai_translate("")
        assert result == "", "Should return empty string for empty input"

        result = openai_translate("   ")
        assert result == "   ", "Should return original text for whitespace-only input"
        print("openai_translate correctly handles empty/whitespace input")

    def test_openai_translate_returns_str_or_none(self):
        """Test openai_translate return type."""
        from src.translators.openai import openai_translate

        # Test with no API key
        from src.translators import openai as openai_module
        original_key = openai_module.config.OPENAI_API_KEY

        try:
            openai_module.config.OPENAI_API_KEY = None
            openai_module._client = None

            result = openai_translate("test text")
            assert result is None or isinstance(result, str), "Should return None or str"
            print("openai_translate return type is correct")
        finally:
            openai_module.config.OPENAI_API_KEY = original_key


class TestFallbackModule:
    """Test fallback translation module."""

    def test_fallback_hash_text(self):
        """Test _hash_text function."""
        from src.translators.fallback import _hash_text

        hash1 = _hash_text("test")
        hash2 = _hash_text("test")
        assert hash1 == hash2, "Same text should produce same hash"

        hash3 = _hash_text("different")
        assert hash1 != hash3, "Different text should produce different hash"
        print("_hash_text function works correctly")

    def test_fallback_get_semaphore(self):
        """Test semaphore creation."""
        from src.translators.fallback import _get_semaphore, MAX_CONCURRENT_TRANSLATIONS
        import asyncio

        semaphore = _get_semaphore()
        assert isinstance(semaphore, asyncio.Semaphore), "Should return asyncio.Semaphore"

        # Second call should return same instance
        semaphore2 = _get_semaphore()
        assert semaphore is semaphore2, "Should return same semaphore instance"
        print("Semaphore creation works correctly")


class TestImageEditorModule:
    """Test image editor module functions."""

    def test_ocr_image_editor_imports(self):
        """Test that image_editor module imports required functions."""
        from src.ocr import image_editor

        assert hasattr(image_editor, 'get_vision_chain'), "Should have get_vision_chain"
        assert hasattr(image_editor, 'extract_text_from_image'), "Should have extract_text_from_image"
        assert hasattr(image_editor, 'edit_image_text_sync'), "Should have edit_image_text_sync"
        assert hasattr(image_editor, 'edit_image_text'), "Should have edit_image_text"
        print("Image editor module has all required functions")


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_basic_module_structure(self):
        """Test basic module structure and imports."""
        try:
            from src.translators import openai
            from src.translators import fallback
            from src.ocr import image_editor
            from src.config import config

            assert openai is not None
            assert fallback is not None
            assert image_editor is not None
            assert config is not None

            print("All key modules imported successfully")
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import required modules: {e}")

    def test_config_is_singleton(self):
        """Test that config is a singleton instance."""
        from src.config import config as config1
        from src.config import config as config2

        assert config1 is config2, "Config should be a singleton"
        print("Config is a singleton instance")

    def test_openai_module_exports(self):
        """Test that openai module exports required functions."""
        from src.translators import openai

        assert hasattr(openai, 'get_client'), "Should export get_client"
        assert hasattr(openai, 'openai_translate'), "Should export openai_translate"
        assert callable(openai.get_client), "get_client should be callable"
        assert callable(openai.openai_translate), "openai_translate should be callable"
        print("OpenAI module exports are correct")

    def test_fallback_module_exports(self):
        """Test that fallback module exports required functions."""
        from src.translators import fallback

        assert hasattr(fallback, 'translate_text_with_fallback'), "Should export translate_text_with_fallback"
        assert hasattr(fallback, '_hash_text'), "Should export _hash_text"
        assert hasattr(fallback, '_get_semaphore'), "Should export _get_semaphore"
        assert callable(fallback.translate_text_with_fallback), "translate_text_with_fallback should be callable"
        print("Fallback module exports are correct")


class TestPackageStructure:
    """Test package structure and organization."""

    def test_src_package_structure(self):
        """Test src package has correct structure."""
        src_dir = os.path.join(os.path.dirname(__file__), '..', 'src')

        required_dirs = [
            'translators',
            'image_editing',
            'ocr',
        ]

        for dir_name in required_dirs:
            dir_path = os.path.join(src_dir, dir_name)
            assert os.path.isdir(dir_path), f"Directory {dir_name} should exist"

            init_file = os.path.join(dir_path, '__init__.py')
            assert os.path.isfile(init_file), f"__init__.py should exist in {dir_name}"

        print("Package structure is correct")

    def test_required_files_exist(self):
        """Test that all required files exist."""
        base_path = os.path.join(os.path.dirname(__file__), '..')

        required_files = [
            'src/config.py',
            'src/translators/openai.py',
            'src/translators/fallback.py',
            'src/translators/__init__.py',
            'src/image_editing/factory.py',
            'src/ocr/image_editor.py',
        ]

        for file_path in required_files:
            full_path = os.path.join(base_path, file_path)
            assert os.path.isfile(full_path), f"File {file_path} should exist"

        print("All required files exist")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
