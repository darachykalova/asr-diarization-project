from faster_whisper import WhisperModel


class ASRService:
    """
    Service for automatic speech recognition using faster-whisper.
    """

    def __init__(self, model_size: str = "base"):
        """
        Loads Whisper model once when the service is created.

        Parameters:
            model_size (str): Whisper model size, for example tiny, base, small.
        """
        self.model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8"
        )

    def transcribe(self, audio_path: str, language: str = "ru") -> list[dict]:
        """
        Transcribes audio file into text segments with word-level timestamps.

        Parameters:
            audio_path (str): Path to normalized audio file.
            language (str): Audio language code.

        Returns:
            list[dict]: List of recognized text segments with words.
        """
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True
        )

        result = []

        for segment in segments:
            text = segment.text.strip()

            if not text:
                continue

            words = []

            if segment.words:
                for word in segment.words:
                    words.append({
                        "word": word.word.strip(),
                        "start": round(word.start, 2),
                        "end": round(word.end, 2),
                        "confidence": round(word.probability, 2)
                    })

            result.append({
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": text,
                "words": words
            })

        return result