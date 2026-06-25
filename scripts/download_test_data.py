"""
Download Russian speech test samples from Mozilla Common Voice (via HuggingFace).

Run ONCE on the host machine (needs internet):
    pip install datasets soundfile
    python scripts/download_test_data.py

Saves audio + reference text pairs to:
    tests/asr_quality/audio/<id>.mp3
    tests/asr_quality/references/<id>.txt

After running, the benchmark script works fully offline inside Docker.

Flags:
    --samples N   number of samples to download (default: 50)
    --split       dataset split: test | validation | train (default: test)
"""

import argparse
import sys
from pathlib import Path

AUDIO_DIR = Path("tests/asr_quality/audio")
REF_DIR = Path("tests/asr_quality/references")


def main(n_samples: int, split: str) -> None:
    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: 'datasets' library not installed.")
        print("       Run: pip install datasets")
        sys.exit(1)

    try:
        import soundfile as sf
    except ImportError:
        print("ERROR: 'soundfile' library not installed.")
        print("       Run: pip install soundfile")
        sys.exit(1)

    import numpy as np

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    REF_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading Common Voice 13 Russian ({split} split, streaming)...")
    print("NOTE: First run requires accepting Mozilla Common Voice terms on HuggingFace.")
    print("      If prompted, create an account at https://huggingface.co and accept terms at:")
    print("      https://huggingface.co/datasets/mozilla-foundation/common_voice_13_0")
    print()

    try:
        ds = load_dataset(
            "mozilla-foundation/common_voice_13_0",
            "ru",
            split=split,
            streaming=True,
            trust_remote_code=True,
        )
    except Exception as exc:
        print(f"ERROR: Could not load dataset: {exc}")
        print()
        print("Alternative: use --dataset golos")
        sys.exit(1)

    saved = 0
    skipped = 0

    for sample in ds:
        if saved >= n_samples:
            break

        sentence = sample.get("sentence", "").strip()
        if not sentence or len(sentence) < 5:
            skipped += 1
            continue

        audio_data = sample.get("audio", {})
        array = audio_data.get("array")
        sr = audio_data.get("sampling_rate", 16000)

        if array is None:
            skipped += 1
            continue

        sample_id = f"cv_{split}_{saved:04d}"
        wav_path = AUDIO_DIR / f"{sample_id}.wav"
        txt_path = REF_DIR / f"{sample_id}.txt"

        sf.write(str(wav_path), np.array(array), sr)
        txt_path.write_text(sentence, encoding="utf-8")

        saved += 1
        print(f"  [{saved}/{n_samples}] {sample_id}: {sentence[:60]}...")

    print()
    print(f"Done. Saved: {saved} samples, skipped: {skipped}.")
    print(f"Audio:      {AUDIO_DIR.resolve()}")
    print(f"References: {REF_DIR.resolve()}")
    print()
    print("Run benchmark inside Docker:")
    print("  docker compose exec worker python scripts/test_asr_quality.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download ASR test data from Common Voice Russian")
    parser.add_argument("--samples", type=int, default=50, help="Number of samples to download")
    parser.add_argument("--split", default="test", choices=["test", "validation", "train"])
    args = parser.parse_args()
    main(args.samples, args.split)
