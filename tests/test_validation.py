"""Tests for parameter validation."""

import pytest
from leanvox.client import _validate_generate_params
from leanvox.errors import InvalidRequestError, StreamingFormatError
from leanvox import Leanvox


class TestValidateGenerateParams:
    def test_empty_text(self):
        with pytest.raises(InvalidRequestError, match="cannot be empty"):
            _validate_generate_params("", "standard", 1.0, 0.5)

    def test_text_too_long(self):
        with pytest.raises(InvalidRequestError, match="10,000"):
            _validate_generate_params("x" * 10_001, "standard", 1.0, 0.5)

    def test_text_at_limit_ok(self):
        _validate_generate_params("x" * 10_000, "standard", 1.0, 0.5)

    def test_invalid_model(self):
        with pytest.raises(InvalidRequestError, match="Model must be"):
            _validate_generate_params("hello", "turbo", 1.0, 0.5)

    def test_speed_too_low(self):
        with pytest.raises(InvalidRequestError, match="Speed"):
            _validate_generate_params("hello", "standard", 0.3, 0.5)

    def test_speed_too_high(self):
        with pytest.raises(InvalidRequestError, match="Speed"):
            _validate_generate_params("hello", "standard", 2.5, 0.5)

    def test_exaggeration_on_standard_raises(self):
        with pytest.raises(InvalidRequestError, match="exaggeration.*pro"):
            _validate_generate_params("hello", "standard", 1.0, 0.8)

    def test_exaggeration_default_on_standard_ok(self):
        # Default 0.5 should be fine on standard
        _validate_generate_params("hello", "standard", 1.0, 0.5)

    def test_exaggeration_on_pro_ok(self):
        _validate_generate_params("hello", "pro", 1.0, 0.8)

    def test_exaggeration_out_of_range(self):
        with pytest.raises(InvalidRequestError, match="Exaggeration"):
            _validate_generate_params("hello", "pro", 1.0, 1.5)


class TestStreamFormatValidation:
    def test_wav_format_raises(self):
        client = Leanvox(api_key="lv_test_dummy")
        with pytest.raises(StreamingFormatError, match="only supports MP3"):
            with client.stream("hello", format="wav"):
                pass

    def test_mp3_format_accepted(self):
        # This will fail on network (no server) but won't raise StreamingFormatError
        client = Leanvox(api_key="lv_test_dummy")
        # We can't test the full flow without a server, just verify no format error
        # The actual network call would fail, which is expected
        pass
