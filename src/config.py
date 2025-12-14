"""
Configuration module for Telegram Signal Translator Bot.

Uses Pydantic Settings to load configuration from .env file.
All environment variables are validated and type-checked.
"""

from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """
    Application configuration loaded from environment variables.

    Environment variables are automatically loaded from .env file.
    All settings are validated using Pydantic.
    """

    # ============ TELEGRAM READER ACCOUNT ============
    READER_API_ID: int = Field(..., description="Telegram API ID for reader account")
    READER_API_HASH: str = Field(..., description="Telegram API hash for reader account")
    READER_PHONE: str = Field(..., description="Phone number for reader account")
    READER_SESSION_FILE: str = Field(
        default="sessions/reader.session",
        description="Session file path for reader account (legacy)"
    )
    READER_SESSION_STRING: Optional[str] = Field(
        default=None,
        description="Telegram session string (preferred over session file)"
    )

    # ============ TELEGRAM PUBLISHER ACCOUNT ============
    PUBLISHER_API_ID: int = Field(..., description="Telegram API ID for publisher account")
    PUBLISHER_API_HASH: str = Field(..., description="Telegram API hash for publisher account")
    PUBLISHER_PHONE: str = Field(..., description="Phone number for publisher account")
    PUBLISHER_SESSION_FILE: str = Field(
        default="sessions/publisher.session",
        description="Session file path for publisher account (legacy)"
    )
    PUBLISHER_SESSION_STRING: Optional[str] = Field(
        default=None,
        description="Telegram session string (preferred over session file)"
    )

    # ============ GROUP IDs ============
    SOURCE_GROUP_ID: int = Field(..., description="Source Telegram group ID (negative, starts with -100)")
    TARGET_GROUP_ID: int = Field(..., description="Target Telegram group ID (negative, starts with -100)")
    SOURCE_ALLOWED_USERS: Optional[str] = Field(
        default=None,
        description="Comma-separated list of allowed user IDs"
    )

    # ============ GEMINI API ============
    GEMINI_API_KEY: str = Field(..., description="Google Gemini API key")
    GEMINI_MODEL: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model to use for translation and OCR"
    )
    GEMINI_IMAGE_MODEL: str = Field(
        default="gemini-2.5-flash-image",
        description="Gemini model for image text editing (Nano Banana Pro: gemini-3-pro-image-preview)"
    )

    # ============ OPENAI API (Optional) ============
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key (optional, for vision OCR)"
    )
    OPENAI_VISION_MODEL: str = Field(
        default="gpt-4o",
        description="OpenAI model to use for vision OCR"
    )
    OPENAI_TRANSLATE_MODEL: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model to use for text translation"
    )
    OPENAI_TRANSLATE_MAX_TOKENS: int = Field(
        default=2000,
        description="Max tokens for translation response"
    )

    # ============ ANTHROPIC API (Optional) ============
    ANTHROPIC_API_KEY: Optional[str] = Field(
        default=None,
        description="Anthropic API key (optional, for vision OCR)"
    )
    ANTHROPIC_VISION_MODEL: str = Field(
        default="claude-sonnet-4-20250514",
        description="Anthropic Claude model to use for vision OCR"
    )

    # ============ VISION PROVIDERS ============
    VISION_PROVIDER: str = Field(
        default="gemini",
        description="Primary vision provider for OCR (gemini, openai, anthropic)"
    )
    VISION_FALLBACK_PROVIDERS: Optional[str] = Field(
        default="openai,anthropic",
        description="Comma-separated fallback providers for OCR"
    )
    VISION_TIMEOUT_SEC: int = Field(
        default=30,
        description="Timeout for vision API requests in seconds"
    )
    VISION_MAX_RETRIES: int = Field(
        default=1,
        description="Max retries per provider before fallback"
    )

    # ============ IMAGE EDITING ============
    IMAGE_EDITOR: str = Field(
        default="openai",
        description="Image editor for text replacement (paddleocr, gemini, openai)"
    )
    IMAGE_EDITOR_FALLBACK: Optional[str] = Field(
        default="gemini",
        description="Fallback image editor if primary fails"
    )
    OPENAI_IMAGE_MODEL: str = Field(
        default="gpt-image-1",
        description="OpenAI model for image editing"
    )

    # ============ GOOGLE TRANSLATE (Optional) ============
    GOOGLE_TRANSLATE_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Translate API key (optional, for fallback)"
    )

    # ============ DATABASE ============
    POSTGRES_USER: str = Field(default="postgres", description="PostgreSQL username")
    POSTGRES_PASSWORD: str = Field(..., description="PostgreSQL password")
    POSTGRES_DB: str = Field(default="signal_bot", description="PostgreSQL database name")
    POSTGRES_HOST: str = Field(default="db", description="PostgreSQL host")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL port")
    SQLALCHEMY_ECHO: bool = Field(
        default=False,
        description="Enable SQLAlchemy SQL query logging"
    )

    # ============ REDIS (Optional) ============
    REDIS_URL: Optional[str] = Field(
        default=None,
        description="Redis connection URL (optional)"
    )

    # ============ APPLICATION ============
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    ENVIRONMENT: str = Field(
        default="production",
        description="Environment name (development, staging, production)"
    )
    MAX_RETRIES: int = Field(
        default=3,
        description="Maximum number of retries for failed operations"
    )
    TIMEOUT_GEMINI_SEC: int = Field(
        default=30,
        description="Timeout for Gemini API requests in seconds"
    )
    TIMEOUT_TELEGRAM_SEC: int = Field(
        default=15,
        description="Timeout for Telegram API requests in seconds"
    )
    API_PORT: int = Field(
        default=8000,
        description="Port for health check HTTP server"
    )

    # ============ MEDIA ============
    MEDIA_DOWNLOAD_DIR: str = Field(
        default="/tmp/signals",
        description="Directory for temporary media downloads"
    )
    MAX_IMAGE_SIZE_MB: int = Field(
        default=50,
        description="Maximum image size to process in megabytes"
    )

    # Pydantic settings configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # ============ VALIDATORS ============

    @field_validator("SOURCE_GROUP_ID", "TARGET_GROUP_ID")
    @classmethod
    def validate_group_id(cls, v: int) -> int:
        """Validate that group IDs are negative (Telegram supergroup format)."""
        if v >= 0:
            raise ValueError(
                f"Group ID must be negative (starts with -100 for supergroups), got {v}"
            )
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the allowed values."""
        allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed_levels:
            raise ValueError(
                f"LOG_LEVEL must be one of {allowed_levels}, got {v}"
            )
        return v_upper

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of the allowed values."""
        allowed_envs = {"development", "staging", "production"}
        v_lower = v.lower()
        if v_lower not in allowed_envs:
            raise ValueError(
                f"ENVIRONMENT must be one of {allowed_envs}, got {v}"
            )
        return v_lower

    @field_validator("VISION_PROVIDER")
    @classmethod
    def validate_vision_provider(cls, v: str) -> str:
        """Validate vision provider is one of the allowed values."""
        allowed = {"gemini", "openai", "anthropic"}
        if v.lower() not in allowed:
            raise ValueError(f"VISION_PROVIDER must be one of {allowed}, got {v}")
        return v.lower()

    @field_validator("IMAGE_EDITOR")
    @classmethod
    def validate_image_editor(cls, v: str) -> str:
        """Validate image editor is one of the allowed values."""
        allowed = {"paddleocr", "gemini", "openai"}
        if v.lower() not in allowed:
            raise ValueError(f"IMAGE_EDITOR must be one of {allowed}, got {v}")
        return v.lower()

    # ============ HELPER PROPERTIES ============

    @property
    def postgres_dsn(self) -> str:
        """
        Build PostgreSQL connection string (DSN).

        Returns:
            PostgreSQL connection URL in format:
            postgresql://user:password@host:port/database
        """
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def postgres_async_dsn(self) -> str:
        """
        Build async PostgreSQL connection string (DSN) for asyncpg.

        Returns:
            PostgreSQL async connection URL in format:
            postgresql+asyncpg://user:password@host:port/database
        """
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def allowed_users_list(self) -> List[int]:
        """
        Parse SOURCE_ALLOWED_USERS string to list of integers.

        Returns:
            List of user IDs, or empty list if SOURCE_ALLOWED_USERS is None/empty.
        """
        if not self.SOURCE_ALLOWED_USERS:
            return []

        try:
            # Split by comma and convert to integers, filtering out empty strings
            return [
                int(user_id.strip())
                for user_id in self.SOURCE_ALLOWED_USERS.split(",")
                if user_id.strip()
            ]
        except ValueError as e:
            raise ValueError(
                f"Invalid SOURCE_ALLOWED_USERS format. "
                f"Expected comma-separated integers, got: {self.SOURCE_ALLOWED_USERS}"
            ) from e

    @property
    def vision_fallback_list(self) -> List[str]:
        """
        Parse VISION_FALLBACK_PROVIDERS into list.

        Returns:
            List of fallback provider names, or empty list if None/empty.
        """
        if not self.VISION_FALLBACK_PROVIDERS:
            return []
        return [p.strip().lower() for p in self.VISION_FALLBACK_PROVIDERS.split(",") if p.strip()]


# ============ SINGLETON INSTANCE ============

# Create singleton config instance for easy import throughout the application
# Usage: from src.config import config
config = Config()
