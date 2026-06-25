"""
Download Russian speech test samples for ASR quality benchmark.

Source: google/fleurs (ru_ru, test split) — public dataset, no account required.
Method:
  1. Downloads test.tsv (0.7 MB) — transcriptions.
  2. Streams audio/test.tar.gz and stops as soon as N WAV files are extracted.
     Typically needs to download only the first 20-50 MB of the 413 MB archive.

Run ONCE on the host machine (needs internet):
    python scripts/download_test_data.py

Flags:
    --samples N   number of samples to save (default: 50)

After running, the benchmark works fully offline inside Docker:
    docker compose exec worker python scripts/test_asr_quality.py --models tiny base
"""

import argparse
import csv
import io
import sys
import tarfile
from pathlib import Path

AUDIO_DIR = Path("tests/asr_quality/audio")
REF_DIR   = Path("tests/asr_quality/references")

FLEURS_BASE = (
    "https://huggingface.co/datasets/google/fleurs/resolve/main/data/ru_ru"
)


def load_transcriptions() -> dict[str, str]:
    """Download test.tsv and return {wav_filename: transcription}."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("ERROR: pip install huggingface_hub"); sys.exit(1)

    print("Downloading test.tsv (0.7 MB)...")
    tsv_path = hf_hub_download(
        repo_id="google/fleurs",
        filename="data/ru_ru/test.tsv",
        repo_type="dataset",
    )

    transcriptions: dict[str, str] = {}
    with open(tsv_path, encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if len(row) < 4:
                continue
            wav_name = row[1].strip()      # e.g. "13632175593719991398.wav"
            text     = row[3].strip()      # normalized transcription
            if wav_name and text:
                transcriptions[wav_name] = text

    print(f"  {len(transcriptions)} entries in TSV")
    return transcriptions


def stream_and_extract(transcriptions: dict[str, str], n_samples: int) -> int:
    """Stream audio/test.tar.gz, save first n_samples matching WAV files."""
    try:
        import requests
    except ImportError:
        print("ERROR: pip install requests"); sys.exit(1)
    try:
        import soundfile as sf
    except ImportError:
        print("ERROR: pip install soundfile"); sys.exit(1)

    url = f"{FLEURS_BASE}/audio/test.tar.gz"
    print(f"Streaming audio/test.tar.gz from HuggingFace (stop after {n_samples} files)...")
    print(f"  {url}")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    REF_DIR.mkdir(parents=True, exist_ok=True)

    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()

    class _StreamAdapter(io.RawIOBase):
        """Wrap requests streaming response into a file-like object for tarfile."""
        def __init__(self, iterator):
            self._iter = iterator
            self._buf  = b""

        def read(self, n=-1):
            if n == -1:
                return b"".join(self._iter)
            while len(self._buf) < n:
                try:
                    self._buf += next(self._iter)
                except StopIteration:
                    break
            out, self._buf = self._buf[:n], self._buf[n:]
            return out

        def readable(self):
            return True

    stream = _StreamAdapter(resp.iter_content(chunk_size=256 * 1024))

    saved    = 0
    scanned  = 0
    bytes_dl = 0

    with tarfile.open(fileobj=stream, mode="r|gz") as tf:
        for member in tf:
            scanned += 1
            if not member.isfile():
                continue

            filename = Path(member.name).name  # strip any directory prefix
            if filename not in transcriptions:
                # still need to advance the stream past this entry
                tf.members = []   # discard buffered members
                continue

            text = transcriptions[filename]
            fileobj = tf.extractfile(member)
            if fileobj is None:
                continue

            raw = fileobj.read()
            bytes_dl += len(raw)

            sample_id = f"fleurs_test_{saved:04d}"
            wav_path  = AUDIO_DIR / f"{sample_id}.wav"
            txt_path  = REF_DIR   / f"{sample_id}.txt"

            # FLEURS audio is stored as WAV inside the tar; write directly
            try:
                audio_array, file_sr = sf.read(io.BytesIO(raw))
                sf.write(str(wav_path), audio_array, file_sr)
            except Exception as e:
                print(f"  [WARN] {filename}: {e}")
                continue

            txt_path.write_text(text, encoding="utf-8")
            saved += 1
            print(f"  [{saved}/{n_samples}] {sample_id}: {text[:70]}")

            if saved >= n_samples:
                break

    print()
    print(f"Done. Saved {saved}/{n_samples} samples (scanned {scanned} tar entries).")
    print(f"  Audio:      {AUDIO_DIR.resolve()}")
    print(f"  References: {REF_DIR.resolve()}")
    print()
    print("Run benchmark:")
    print("  docker compose exec worker python scripts/test_asr_quality.py --models tiny base")
    return saved


def main(n_samples: int) -> None:
    transcriptions = load_transcriptions()
    stream_and_extract(transcriptions, n_samples)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=50)
    args = ap.parse_args()
    main(args.samples)
