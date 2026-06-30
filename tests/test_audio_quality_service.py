"""
Unit tests for automatic Whisper model selection (services/audio_quality_service.py).

Pure-logic functions — no audio I/O, no ML deps — safe to run in CI.
"""
import pytest

from services.audio_quality_service import (
    MODEL_CLEAN,
    MODEL_OK,
    MODEL_POOR,
    SNR_CLEAN_DB,
    SNR_OK_DB,
    WhisperModelChoice,
    resolve_user_model,
    select_model_by_snr,
)


# --------------------------------------------------------------------------
# select_model_by_snr — SNR (dB) -> model tier
# --------------------------------------------------------------------------

def test_high_snr_selects_tiny():
    assert select_model_by_snr(25.0) == MODEL_CLEAN


def test_snr_exactly_at_clean_threshold_selects_tiny():
    # boundary is inclusive (>=)
    assert select_model_by_snr(SNR_CLEAN_DB) == MODEL_CLEAN


def test_mid_snr_selects_base():
    assert select_model_by_snr(15.0) == MODEL_OK


def test_snr_exactly_at_ok_threshold_selects_base():
    assert select_model_by_snr(SNR_OK_DB) == MODEL_OK


def test_low_snr_selects_large():
    assert select_model_by_snr(5.0) == MODEL_POOR


def test_zero_snr_selects_large():
    assert select_model_by_snr(0.0) == MODEL_POOR


def test_just_below_clean_threshold_is_base():
    assert select_model_by_snr(SNR_CLEAN_DB - 0.1) == MODEL_OK


def test_just_below_ok_threshold_is_large():
    assert select_model_by_snr(SNR_OK_DB - 0.1) == MODEL_POOR


# --------------------------------------------------------------------------
# resolve_user_model — user override -> internal faster-whisper id
# --------------------------------------------------------------------------

def test_none_returns_none():
    assert resolve_user_model(None) is None


def test_tiny_alias():
    assert resolve_user_model("tiny") == "tiny"


def test_base_alias():
    assert resolve_user_model("base") == "base"


def test_large_maps_to_large_v2():
    assert resolve_user_model("large") == "large-v2"


def test_enum_value_resolves():
    assert resolve_user_model(WhisperModelChoice.large) == "large-v2"


def test_uppercase_is_normalised():
    assert resolve_user_model("LARGE") == "large-v2"


def test_surrounding_whitespace_is_stripped():
    assert resolve_user_model("  tiny  ") == "tiny"


def test_unknown_model_raises_value_error():
    with pytest.raises(ValueError):
        resolve_user_model("huge")


def test_empty_string_raises_value_error():
    with pytest.raises(ValueError):
        resolve_user_model("")
