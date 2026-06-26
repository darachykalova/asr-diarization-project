"""
Audio quality estimation + automatic Whisper model selection.

No reference signal is available (we only have the user's upload), so SNR is
estimated with a no-reference, energy-percentile method: frame the waveform,
take per-frame RMS energy, treat a low percentile as the noise floor and a high
percentile as the speech level. Their ratio in dB is a robust proxy for "how
clean / how audible" the recording is.

The estimated SNR maps to a Whisper model tier:
  - clean audio  -> tiny  (fast, enough quality)
  - average      -> base
  - noisy / poor -> large (slow, best quality)

This lets the system spend heavy compute only on recordings that actually need
it. The user can always override the choice with an explicit model.
"""

import logging

logger = logging.getLogger(__name__)

# SNR thresholds in dB (defaults). Higher SNR = cleaner audio.
SNR_CLEAN_DB = 20.0   # >= this -> tiny
SNR_OK_DB = 10.0      # >= this -> base, below -> large

# Internal faster-whisper model ids chosen per tier.
MODEL_CLEAN = "tiny"
MODEL_OK = "base"
MODEL_POOR = "large-v2"

# What a user may pass via the API, mapped to internal faster-whisper ids.
USER_MODEL_ALIASES = {
    "tiny": "tiny",
    "base": "base",
    "large": "large-v2",
    "large-v2": "large-v2",
}


def compute_snr_db(wav_path: str) -> float:
    """
    Estimate signal-to-noise ratio (dB) of a 16 kHz mono WAV with a
    no-reference, energy-percentile method.

    Returns a high value (clean) if the file is too short or unreadable, so a
    failure here never blocks transcription — it just defers to a safe model.
    """
    try:
        import numpy as np
        import soundfile as sf

        audio, sr = sf.read(wav_path)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        frame_len = max(1, int(0.02 * sr))  # 20 ms frames
        n_frames = len(audio) // frame_len
        if n_frames < 5:
            return 30.0  # too short to judge — assume clean

        frames = audio[: n_frames * frame_len].reshape(n_frames, frame_len)
        energies = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)

        noise = float(np.percentile(energies, 10))
        signal = float(np.percentile(energies, 90))
        noise = max(noise, 1e-9)

        snr_db = 20.0 * np.log10(signal / noise)
        return round(float(snr_db), 1)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("SNR estimation failed for %s: %s", wav_path, exc)
        return 30.0


def select_model_by_snr(snr_db: float) -> str:
    """Map an estimated SNR (dB) to an internal faster-whisper model id."""
    if snr_db >= SNR_CLEAN_DB:
        return MODEL_CLEAN
    if snr_db >= SNR_OK_DB:
        return MODEL_OK
    return MODEL_POOR


def resolve_user_model(value: str | None) -> str | None:
    """
    Validate and normalise a user-supplied model name.

    Returns the internal faster-whisper id, or None if no override was given.
    Raises ValueError if the value is not a recognised model.
    """
    if value is None:
        return None
    key = value.strip().lower()
    if key not in USER_MODEL_ALIASES:
        allowed = ", ".join(sorted(set(USER_MODEL_ALIASES.keys())))
        raise ValueError(f"Unknown whisper_model '{value}'. Allowed: {allowed}")
    return USER_MODEL_ALIASES[key]
