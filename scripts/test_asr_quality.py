"""
ASR quality benchmark: measures WER, CER and RTF for Whisper model sizes.

Usage (inside Docker):
    docker compose exec worker python scripts/test_asr_quality.py
    docker compose exec worker python scripts/test_asr_quality.py --models tiny base small
    docker compose exec worker python scripts/test_asr_quality.py --audio tests/asr_quality/audio/

Output:
    - Formatted table to stdout
    - JSON results to tests/asr_quality/results/YYYY-MM-DD_HH-MM.json

Metrics:
    WER  — Word Error Rate   (% ошибочных слов, главная метрика ASR)
    CER  — Character Error Rate (% ошибочных символов, важно для русского)
    RTF  — Real-Time Factor  (время_обработки / длительность_аудио, <1 = быстрее реального)
    Score — (1 - WER) × 100, читаемый «процент правильных слов»
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.WARNING)

TESTS_DIR = Path("tests/asr_quality")
AUDIO_DIR = TESTS_DIR / "audio"
REF_DIR = TESTS_DIR / "references"
RESULTS_DIR = TESTS_DIR / "results"

MODEL_CACHE_DIR = Path(os.getenv("MODEL_CACHE_DIR", "/app/models"))
WHISPER_CACHE = MODEL_CACHE_DIR / "whisper"

DEFAULT_MODELS = ["base"]


# ---------------------------------------------------------------------------
# Text normalization for Russian
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    text = text.lower()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@dataclass
class TestSample:
    name: str
    audio_path: Path
    reference: str


def load_test_samples(audio_dir: Path) -> list[TestSample]:
    samples: list[TestSample] = []

    for audio_path in sorted(audio_dir.glob("*")):
        if audio_path.suffix.lower() not in {".mp3", ".wav", ".ogg", ".flac", ".m4a"}:
            continue

        ref_path = REF_DIR / audio_path.with_suffix(".txt").name
        if not ref_path.exists():
            print(f"  [SKIP] No reference for {audio_path.name} — add {ref_path}")
            continue

        reference = ref_path.read_text(encoding="utf-8").strip()
        if not reference:
            print(f"  [SKIP] Empty reference for {audio_path.name}")
            continue

        samples.append(TestSample(
            name=audio_path.stem,
            audio_path=audio_path,
            reference=reference,
        ))

    return samples


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def transcribe(audio_path: Path, model_size: str) -> tuple[str, float, float]:
    """Returns (text, elapsed_seconds, audio_duration_seconds)."""
    from faster_whisper import WhisperModel

    model_path = str(WHISPER_CACHE / f"models--Systran--faster-whisper-{model_size}")
    if not Path(model_path).exists():
        raise FileNotFoundError(
            f"Model 'faster-whisper-{model_size}' not found at {model_path}.\n"
            f"Download it by running (with internet access):\n"
            f"  docker compose exec -e HF_HUB_OFFLINE=0 worker python -c \""
            f"from faster_whisper import WhisperModel; "
            f"WhisperModel('{model_size}', device='cpu', download_root='{WHISPER_CACHE}')\""
        )

    model = WhisperModel(
        model_size,
        device="cpu",
        compute_type="int8",
        download_root=str(WHISPER_CACHE),
    )

    t_start = time.perf_counter()
    segments, info = model.transcribe(
        str(audio_path),
        beam_size=5,
        word_timestamps=False,
        vad_filter=True,
    )
    text = " ".join(seg.text.strip() for seg in segments)
    elapsed = time.perf_counter() - t_start

    return text, elapsed, info.duration


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class SampleResult:
    name: str
    model: str
    reference: str
    hypothesis: str
    wer: float
    cer: float
    rtf: float
    duration_sec: float
    elapsed_sec: float


def compute_metrics(sample: TestSample, model_size: str) -> SampleResult | None:
    try:
        import jiwer
    except ImportError:
        print("ERROR: jiwer not installed. Run: pip install jiwer")
        sys.exit(1)

    try:
        hypothesis, elapsed, duration = transcribe(sample.audio_path, model_size)
    except FileNotFoundError as exc:
        print(f"  [MISS] {exc}")
        return None
    except Exception as exc:
        print(f"  [ERR]  {sample.name} / {model_size}: {exc}")
        return None

    ref_norm = _normalize(sample.reference)
    hyp_norm = _normalize(hypothesis)

    wer = jiwer.wer(ref_norm, hyp_norm)
    cer = jiwer.cer(ref_norm, hyp_norm)
    rtf = elapsed / duration if duration > 0 else 0.0

    return SampleResult(
        name=sample.name,
        model=model_size,
        reference=sample.reference,
        hypothesis=hypothesis,
        wer=round(wer, 4),
        cer=round(cer, 4),
        rtf=round(rtf, 3),
        duration_sec=round(duration, 2),
        elapsed_sec=round(elapsed, 2),
    )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_detail(results: list[SampleResult]) -> None:
    if not results:
        return
    print()
    print("ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ ПО ФАЙЛАМ")
    print("=" * 90)
    for r in results:
        print(f"\n  Файл:     {r.name}")
        print(f"  Модель:   {r.model}")
        print(f"  WER:      {r.wer * 100:.1f}%   CER: {r.cer * 100:.1f}%   RTF: {r.rtf:.2f}x")
        print(f"  Длина:    {r.duration_sec:.1f}с → обработка {r.elapsed_sec:.1f}с")
        print(f"  Эталон:   {r.reference}")
        print(f"  Гипотеза: {r.hypothesis}")
        err_words = []
        ref_words = _normalize(r.reference).split()
        hyp_words = _normalize(r.hypothesis).split()
        for w in ref_words:
            if w not in hyp_words:
                err_words.append(w)
        if err_words:
            print(f"  Пропущено / искажено: {', '.join(err_words[:10])}")


def print_summary(results: list[SampleResult], models: list[str]) -> None:
    print()
    print("СВОДНАЯ ТАБЛИЦА ПО МОДЕЛЯМ")
    print("=" * 72)
    header = f"{'Модель':<12} {'Файлов':>7} {'WER':>8} {'CER':>8} {'Score':>8} {'RTF':>8} {'Статус':>10}"
    print(header)
    print("-" * 72)

    for model in models:
        model_results = [r for r in results if r.model == model]
        if not model_results:
            print(f"{model:<12} {'—':>7} {'—':>8} {'—':>8} {'—':>8} {'—':>8} {'нет модели':>10}")
            continue

        avg_wer = sum(r.wer for r in model_results) / len(model_results)
        avg_cer = sum(r.cer for r in model_results) / len(model_results)
        avg_rtf = sum(r.rtf for r in model_results) / len(model_results)
        score = (1 - avg_wer) * 100

        status = "✓ хорошо" if avg_wer < 0.1 else ("~ приемл." if avg_wer < 0.25 else "✗ плохо")

        print(
            f"{model:<12} {len(model_results):>7} "
            f"{avg_wer * 100:>7.1f}% {avg_cer * 100:>7.1f}% "
            f"{score:>7.1f}% {avg_rtf:>7.2f}x "
            f"{status:>10}"
        )

    print("-" * 72)
    print()
    print("  WER   — Word Error Rate (% ошибочных слов; ниже = лучше)")
    print("  CER   — Character Error Rate (% ошибочных символов)")
    print("  Score — процент правильно распознанных слов = (1 - WER) × 100")
    print("  RTF   — Real-Time Factor: 1.0x = реальное время, 0.5x = вдвое быстрее")


def save_results(results: list[SampleResult]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    out_path = RESULTS_DIR / f"{ts}.json"
    data = [asdict(r) for r in results]
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="ASR quality benchmark for Whisper models")
    parser.add_argument(
        "--models", nargs="+", default=DEFAULT_MODELS,
        metavar="SIZE",
        help="Model sizes to test, e.g. --models tiny base small (default: base)",
    )
    parser.add_argument(
        "--audio", default=str(AUDIO_DIR),
        help=f"Directory with audio test files (default: {AUDIO_DIR})",
    )
    parser.add_argument(
        "--detail", action="store_true",
        help="Print per-sample hypothesis vs reference",
    )
    args = parser.parse_args()

    audio_dir = Path(args.audio)
    if not audio_dir.exists():
        print(f"ERROR: Audio directory not found: {audio_dir}")
        print(f"       Place test audio files in {AUDIO_DIR}")
        sys.exit(1)

    samples = load_test_samples(audio_dir)
    if not samples:
        print(f"No test samples found in {audio_dir}.")
        print(f"Add audio files + matching .txt references in {REF_DIR}")
        print()
        print("Quick start: the 15-second example is already included.")
        print("For more data run: python scripts/download_test_data.py --samples 50")
        sys.exit(0)

    print(f"Тест ASR качества | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Файлов: {len(samples)} | Модели: {', '.join(args.models)}")
    print()

    all_results: list[SampleResult] = []

    for model_size in args.models:
        print(f"[{model_size}] Запуск...")
        for sample in samples:
            print(f"  → {sample.name} ({sample.audio_path.stat().st_size // 1024} KB)...", end=" ", flush=True)
            result = compute_metrics(sample, model_size)
            if result:
                all_results.append(result)
                print(f"WER={result.wer * 100:.1f}% RTF={result.rtf:.2f}x")
            else:
                print("пропущен")

    if not all_results:
        print("\nНет результатов. Проверьте наличие моделей.")
        sys.exit(1)

    if args.detail:
        print_detail(all_results)

    print_summary(all_results, args.models)

    out_path = save_results(all_results)
    print(f"Результаты сохранены: {out_path}")


if __name__ == "__main__":
    main()
