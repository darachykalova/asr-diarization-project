import subprocess
from pathlib import Path

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".webm"}
SUPPORTED_CONTENT_TYPES = {
    "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3",
    "audio/flac", "audio/x-flac", "audio/ogg", "audio/opus",
    "audio/mp4", "audio/x-m4a", "audio/aac", "audio/webm",
    "video/webm", "application/octet-stream",
}
MAX_DURATION_SEC = 4 * 3600  # 4 hours


def check_audio_file(path: str, filename: str, content_type: str | None = None) -> None:
    ext = Path(filename).suffix.lower()
    if ext and ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file format '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise ValueError(f"Cannot read audio file: {result.stderr.strip()}")

    try:
        duration = float(result.stdout.strip())
    except (ValueError, TypeError):
        return  # ffprobe didn't return duration — skip check

    if duration > MAX_DURATION_SEC:
        hours = duration / 3600
        raise ValueError(
            f"Audio duration {hours:.1f}h exceeds the 4-hour limit."
        )


def normalize_audio(input_path: str, output_path: str) -> str:
    """
    Converts input audio file to 16kHz mono WAV using ffmpeg.

    Parameters:
        input_path (str): Path to the original audio file.
        output_path (str): Path where normalized WAV file will be saved.

    Returns:
        str: Path to the normalized audio file.
    """
    input_file = Path(input_path)
    output_file = Path(output_path)

    if not input_file.exists():
        raise FileNotFoundError(f"Input audio file not found: {input_path}")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
        "-y",
        "-i", str(input_file),
        "-ar", "16000",
        "-ac", "1",
        str(output_file)
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return str(output_file)
