import logging
import math
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

CHUNK_SEC = 300          # target chunk size: 5 minutes
NO_SPLIT_SEC = 360       # files ≤ 6 min are not split
MIN_TAIL_SEC = 120       # tail < 2 min → merge with previous chunk
SILENCE_WINDOW_SEC = 30  # search for silence ±30 s around each boundary
MIN_SILENCE_SEC = 0.3    # gaps shorter than this are ignored by VAD


def _get_silence_regions(wav_path: str, total_sec: float) -> list[tuple[float, float]] | None:
    """
    Use pyannote's cached segmentation model to find silence (non-speech) regions.

    Returns list of (start_sec, end_sec) silence intervals, or None if VAD fails
    (caller falls back to energy-based detection).

    The pyannote pipeline is already loaded and cached by the worker process for
    diarization, so this reuses the same in-memory object at no extra cost.
    """
    try:
        import numpy as np
        import torch
        from scipy.io import wavfile

        from services.model_cache import get_pyannote_pipeline

        pipeline = get_pyannote_pipeline()

        sample_rate, audio = wavfile.read(wav_path)
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.int32:
            audio = audio.astype(np.float32) / 2147483648.0
        if audio.ndim == 1:
            audio = np.expand_dims(audio, axis=0)
        else:
            audio = audio.T
        waveform = torch.from_numpy(audio)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        waveform = waveform.to(device)

        audio_file = {"waveform": waveform, "sample_rate": int(sample_rate)}

        # _segmentation is the pyannote Inference wrapper around segmentation-3.0.
        # It returns a SlidingWindowFeature of shape (n_frames, n_speakers) with
        # per-frame speech probabilities. Taking the max across speaker channels
        # gives us a per-frame "is someone speaking?" probability.
        segmentations = pipeline._segmentation(audio_file)
        speech_prob = segmentations.data.max(axis=1)
        sliding_window = segmentations.sliding_window

        # Binarize: build a list of speech (start, end) intervals.
        THRESHOLD = 0.5
        speech_segs: list[tuple[float, float]] = []
        in_speech = False
        seg_start = 0.0

        for i, prob in enumerate(speech_prob):
            t = sliding_window[i].middle
            if prob > THRESHOLD and not in_speech:
                in_speech = True
                seg_start = t
            elif prob <= THRESHOLD and in_speech:
                in_speech = False
                speech_segs.append((seg_start, t))
        if in_speech:
            speech_segs.append((seg_start, total_sec))

        # Invert speech → silence gaps.
        silence: list[tuple[float, float]] = []
        prev_end = 0.0
        for start, end in speech_segs:
            gap = start - prev_end
            if gap >= MIN_SILENCE_SEC:
                silence.append((prev_end, start))
            prev_end = max(prev_end, end)
        if total_sec - prev_end >= MIN_SILENCE_SEC:
            silence.append((prev_end, total_sec))

        logger.info("VAD: found %d silence regions in %.1f s audio", len(silence), total_sec)
        return silence

    except Exception as exc:
        logger.warning("VAD (pyannote) failed: %s — falling back to energy-based", exc)
        return None


def _find_cut_vad(target_sec: float, silence_regions: list[tuple[float, float]]) -> float | None:
    """
    Return the centre of the silence region closest to target_sec (within ±SILENCE_WINDOW_SEC).
    Returns None if no suitable silence region is found.
    """
    best_cut: float | None = None
    best_dist = float("inf")
    for start, end in silence_regions:
        center = (start + end) / 2.0
        dist = abs(center - target_sec)
        if dist <= SILENCE_WINDOW_SEC and dist < best_dist:
            best_dist = dist
            best_cut = center
    return best_cut


def _find_cut_energy(audio, sr: int, target_sec: float) -> float:
    """
    Fallback: return the quietest 100 ms frame within ±SILENCE_WINDOW_SEC of target_sec.
    """
    import numpy as np

    frame_len = max(1, int(0.1 * sr))
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

    Strategy:
      1. Try VAD via pyannote to find true speech/silence boundaries.
      2. For each 5-min boundary, pick the centre of the nearest silence region.
      3. If VAD fails, fall back to energy-based minimum-energy frame.

    Returns a list of (temp_wav_path, offset_sec) tuples.
    If the file is short enough or splitting fails entirely, returns [(wav_path, 0.0)].
    Callers must delete temp files (any path that differs from wav_path).
    """
    try:
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

        silence_regions = _get_silence_regions(wav_path, total_sec)

        cut_secs = [0.0]
        for target in boundary_targets:
            if silence_regions is not None:
                cut = _find_cut_vad(target, silence_regions)
                if cut is None:
                    logger.info(
                        "Chunking: no VAD silence near %.0f s, using energy fallback", target
                    )
                    cut = _find_cut_energy(audio, sr, target)
                else:
                    logger.info("Chunking: VAD cut at %.2f s (target %.0f s)", cut, target)
            else:
                cut = _find_cut_energy(audio, sr, target)
            cut_secs.append(cut)
        cut_secs.append(total_sec)

        # Merge tail chunk if it's too short.
        if len(cut_secs) >= 3 and (cut_secs[-1] - cut_secs[-2]) < MIN_TAIL_SEC:
            removed = cut_secs.pop(-2)
            logger.info(
                "Chunking: tail %.1f s < %.0f s, merged with previous",
                total_sec - removed, MIN_TAIL_SEC,
            )

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
                "Chunking: chunk %d → %.1f–%.1f s (%.1f s)",
                i + 1, cut_secs[i], cut_secs[i + 1], cut_secs[i + 1] - cut_secs[i],
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
