import json
import subprocess
from pathlib import Path


class VADService:
    """
    Service for voice activity detection.

    Current version is a placeholder:
    it returns one speech segment for the whole audio duration.
    Later this service will be replaced with real Silero VAD.
    """

    def get_audio_duration(self, audio_path: str) -> float:
        """
        Gets audio duration in seconds using ffprobe.

        Parameters:
            audio_path (str): Path to audio file.

        Returns:
            float: Audio duration in seconds.
        """
        audio_file = Path(audio_path)

        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        command = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(audio_file)
        ]

        completed_process = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )

        metadata = json.loads(completed_process.stdout)

        duration = float(metadata["format"]["duration"])

        return round(duration, 2)

    def detect_speech(self, audio_path: str) -> list[dict]:
        """
        Detects speech segments in audio.

        Current placeholder returns the whole audio as one speech segment.

        Parameters:
            audio_path (str): Path to normalized audio file.

        Returns:
            list[dict]: List of speech segments with start and end time.
        """
        duration = self.get_audio_duration(audio_path)

        return [
            {
                "start": 0.0,
                "end": duration
            }
        ]