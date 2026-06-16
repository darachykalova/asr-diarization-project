import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_longest_segment(
    audio_path: str,
    segments: list[dict],
    speaker_label: str,
    output_path: str,
    min_duration: float = 3.0
) -> str | None:
    speaker_segments = [
        segment
        for segment in segments
        if segment.get("speaker") == speaker_label
    ]

    if not speaker_segments:
        return None

    longest_segment = max(
        speaker_segments,
        key=lambda segment: segment["end"] - segment["start"]
    )

    duration = longest_segment["end"] - longest_segment["start"]

    if duration < min_duration:
        logger.warning(
            "Speaker %s has no segment >= %.2f sec",
            speaker_label,
            min_duration
        )
        return None

    Path(output_path).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            audio_path,
            "-ss",
            str(longest_segment["start"]),
            "-t",
            str(duration),
            "-ar",
            "16000",
            "-ac",
            "1",
            output_path
        ],
        check=True,
        capture_output=True
    )

    return output_path