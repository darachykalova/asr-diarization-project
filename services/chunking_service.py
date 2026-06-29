import logging
import math
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

CHUNK_SEC = 300          # target chunk size: 5 minutes
NO_SPLIT_SEC = 360       # files ≤ 6 min are not split
MIN_TAIL_SEC = 120       # tail < 2 min → merge with previous chunk
SILENCE_WINDOW_SEC = 30  # search for silence ±30 s around each boundary


def _find_silence_near(audio, sr: int, target_sec: float) -> float:
    """Return the quietest cut point (in seconds) within ±SILENCE_WINDOW_SEC of target_sec."""
    import numpy as np

    frame_len = max(1, int(0.1 * sr))  # 100 ms frames
    center = int(target_sec * sr)
    half_win = int(SILENCE_WINDOW_SEC * sr)
    start = max(0, center - half_win)
    end = min(len(audio), center + half_win)

    segment = audio[start:end]
    n_frames = len(segment) // frame_len
    if n_frames == 0:
        return target_sec

    frames = segment[: n_frames * frame_len].reshape(n_frames, frame_len)
    energies = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
    quietest = int(energies.argmin())
    cut_sample = start + quietest * frame_len + frame_len // 2
    return cut_sample / sr


def split_audio(wav_path: str) -> list[tuple[str, float]]:
    """
    Split a 16 kHz mono WAV into chunks, cutting at silence boundaries.

    Returns a list of (temp_wav_path, offset_sec) tuples.
    If the file is short enough or splitting fails, returns [(wav_path, 0.0)].
    Callers must delete temp files (any path that differs from wav_path).
    """
    try:
        import numpy as np
        import soundfile as sf

        audio, sr = sf.read(wav_path)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        total_sec = len(audio) / sr

        if total_sec <= NO_SPLIT_SEC:
            logger.info("Chunking: %.1f s ≤ %.0f s threshold, no split", total_sec, NO_SPLIT_SEC)
            return [(wav_path, 0.0)]

        n_chunks = math.ceil(total_sec / CHUNK_SEC)
        boundary_targets = [i * CHUNK_SEC for i in range(1, n_chunks)]

        cut_secs = [0.0]
        for target in boundary_targets:
            cut = _find_silence_near(audio, sr, target)
            cut_secs.append(cut)
        cut_secs.append(total_sec)

        # Merge tail chunk if it's too short
        if len(cut_secs) >= 3 and (cut_secs[-1] - cut_secs[-2]) < MIN_TAIL_SEC:
            removed = cut_secs.pop(-2)
            logger.info("Chunking: tail %.1f s < %.0f s, merged with previous", total_sec - removed, MIN_TAIL_SEC)

        chunks: list[tuple[str, float]] = []
        for i in range(len(cut_secs) - 1):
            start_s = int(cut_secs[i] * sr)
            end_s = int(cut_secs[i + 1] * sr)
            chunk_audio = audio[start_s:end_s]

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            tmp.close()
            sf.write(tmp.name, chunk_audio, sr, subtype="PCM_16")
            chunks.append((tmp.name, cut_secs[i]))
            logger.info(
                "Chunking: chunk %d → %.1f–%.1f s (%.1f s) → %s",
                i + 1, cut_secs[i], cut_secs[i + 1], cut_secs[i + 1] - cut_secs[i], tmp.name,
            )

        logger.info("Chunking: split %.1f s into %d chunks", total_sec, len(chunks))
        return chunks

    except Exception as exc:
        logger.warning("Chunking failed (%s), processing as single file", exc)
        return [(wav_path, 0.0)]


def delete_chunk_files(chunks: list[tuple[str, float]], original_path: str) -> None:
    """Delete temp chunk files, skipping the original wav."""
    for path, _ in chunks:
        if path != original_path:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass
