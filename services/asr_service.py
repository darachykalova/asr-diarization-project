import os
from typing import Optional

from faster_whisper import WhisperModel

_MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "/app/models")


class ASRService:
    """
    Service for automatic speech recognition using faster-whisper.

    Supports multilingual transcription.
    If language is None, Whisper detects language automatically.
    """

    def __init__(self, model_size: str = "base"):
        self.model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            download_root=os.path.join(_MODEL_CACHE_DIR, "whisper"),
        )

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None
    ) -> list[dict]:
        """
        Transcribes audio file into text segments with word-level timestamps.

        Parameters:
            audio_path (str): Path to normalized audio file.
            language (Optional[str]): Audio language code.
                Examples:
                - None: auto language detection
                - "ru": Russian
                - "es": Spanish
                - "de": German
                - "fr": French
                - "en": English

        Returns:
            list[dict]: List of recognized text segments with words.
        """
        transcribe_kwargs = {
            "word_timestamps": True
        }

        if language:
            transcribe_kwargs["language"] = language

        segments, info = self.model.transcribe(
            audio_path,
            **transcribe_kwargs
        )

        result = []

        for segment in segments:
            text = segment.text.strip()

            if not text:
                continue

            words = []

            if segment.words:
                for word in segment.words:
                    words.append(
                        {
                            "word": word.word.strip(),
                            "start": round(word.start, 2),
                            "end": round(word.end, 2),
                            "confidence": round(word.probability, 2)
                        }
                    )

            result.append(
                {
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "text": text,
                    "words": words
                }
            )

        return result