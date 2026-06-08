from pathlib import Path
import subprocess


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