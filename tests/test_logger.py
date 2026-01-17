"""Tests for logger utilities."""

from src.utils.logger import SENSITIVE_PATTERNS, mask_sensitive_data


class TestMaskSensitiveData:
    """Tests for mask_sensitive_data structlog processor."""

    def test_masks_api_key(self):
        """Test that api_key values are masked."""
        event = {"error": "api_key=secret123"}
        result = mask_sensitive_data(None, None, event)
        assert "secret123" not in result["error"]
        assert "MASKED" in result["error"]

    def test_masks_token(self):
        """Test that token values are masked."""
        event = {"msg": "token: abc123xyz"}
        result = mask_sensitive_data(None, None, event)
        assert "abc123xyz" not in result["msg"]
        assert "MASKED" in result["msg"]

    def test_masks_password(self):
        """Test that password values are masked."""
        event = {"data": "password=mysecretpass"}
        result = mask_sensitive_data(None, None, event)
        assert "mysecretpass" not in result["data"]
        assert "MASKED" in result["data"]

    def test_masks_bearer_token(self):
        """Test that bearer tokens are masked."""
        event = {"auth": "Bearer eyJhbGciOiJIUzI1NiJ9"}
        result = mask_sensitive_data(None, None, event)
        assert "eyJhbGciOiJIUzI1NiJ9" not in result["auth"]
        assert "MASKED" in result["auth"]

    def test_masks_secret(self):
        """Test that secret values are masked."""
        event = {"config": "secret: my_secret_value"}
        result = mask_sensitive_data(None, None, event)
        assert "my_secret_value" not in result["config"]
        assert "MASKED" in result["config"]

    def test_masks_authorization(self):
        """Test that authorization values are masked."""
        event = {"header": "authorization=Bearer abc123"}
        result = mask_sensitive_data(None, None, event)
        assert "Bearer abc123" not in result["header"]
        assert "MASKED" in result["header"]

    def test_preserves_non_sensitive_data(self):
        """Test that non-sensitive data is preserved."""
        event = {"user": "john", "action": "login", "status": "success"}
        result = mask_sensitive_data(None, None, event)
        assert result == event

    def test_handles_non_string_values(self):
        """Test that non-string values are passed through."""
        event = {"count": 42, "active": True, "data": None}
        result = mask_sensitive_data(None, None, event)
        assert result == event

    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        event = {"err": "API_KEY=secret", "auth": "TOKEN=abc123"}
        result = mask_sensitive_data(None, None, event)
        assert "secret" not in result["err"]
        assert "abc123" not in result["auth"]

    def test_multiple_patterns_in_one_string(self):
        """Test that multiple sensitive values in one string are all masked."""
        event = {"config": "api_key=secret123 token:abc456 password=pass789"}
        result = mask_sensitive_data(None, None, event)
        assert "secret123" not in result["config"]
        assert "abc456" not in result["config"]
        assert "pass789" not in result["config"]
        assert result["config"].count("MASKED") == 3

    def test_different_separators(self):
        """Test that patterns work with different separators (=, :)."""
        event = {
            "config1": "api_key=value1",
            "config2": "api_key: value2",
            "config3": "token=value3",
            "config4": "token: value4",
        }
        result = mask_sensitive_data(None, None, event)
        for key in event.keys():
            assert "value" not in result[key]
            assert "MASKED" in result[key]

    def test_handles_underscores_and_hyphens(self):
        """Test that api_key and api-key patterns are both matched."""
        event = {"config": "api_key=secret1 api-key=secret2"}
        result = mask_sensitive_data(None, None, event)
        assert "secret1" not in result["config"]
        assert "secret2" not in result["config"]
        assert result["config"].count("MASKED") == 2

    def test_masks_json_format(self):
        """Test that JSON-formatted secrets are masked."""
        event = {"config": '"api_key": "secret123"'}
        result = mask_sensitive_data(None, None, event)
        assert "secret123" not in result["config"]
        assert "MASKED" in result["config"]

    def test_masks_session_string(self):
        """Test that session strings are masked."""
        event = {"session": "session_string=ABC123DEF456GHI789JKL012MNO"}
        result = mask_sensitive_data(None, None, event)
        assert "ABC123DEF456GHI789JKL012MNO" not in result["session"]
        assert "MASKED" in result["session"]

    def test_masks_phone_numbers(self):
        """Test that phone numbers are masked."""
        event = {"contact": "Phone: +1 234-567-8901"}
        result = mask_sensitive_data(None, None, event)
        assert "234-567-8901" not in result["contact"]
        assert "MASKED" in result["contact"]

    def test_sensitive_patterns_count(self):
        """Test that expected number of patterns are defined."""
        # Should have at least 6 base patterns + new patterns
        assert len(SENSITIVE_PATTERNS) >= 6

    def test_masks_preserve_prefix(self):
        """Test that masking preserves the pattern prefix."""
        event = {"log": "Found api_key=secret123"}
        result = mask_sensitive_data(None, None, event)
        assert "api_key=" in result["log"]
        assert "MASKED" in result["log"]
        assert "secret123" not in result["log"]

    def test_bearer_token_with_space(self):
        """Test that bearer token pattern requires space separator."""
        event = {"auth": "Bearer token123"}
        result = mask_sensitive_data(None, None, event)
        assert "token123" not in result["auth"]
        assert "Bearer ***MASKED***" in result["auth"]

    def test_handles_mixed_content(self):
        """Test masking in strings with mixed sensitive and normal content."""
        event = {"message": "User logged in with token=abc123, status: success"}
        result = mask_sensitive_data(None, None, event)
        assert "abc123" not in result["message"]
        assert "MASKED" in result["message"]
        assert "User logged in" in result["message"]
        assert "status: success" in result["message"]
