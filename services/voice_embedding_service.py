import logging
import wave

import numpy as np

logger = logging.getLogger(__name__)


class VoiceEmbeddingService:
    VECTOR_SIZE = 512

    def __init__(self):
        logger.info("VoiceEmbeddingService initialized without TorchCodec.")

    def is_available(self) -> bool:
        return True

    def extract_embedding(
        self,
        audio_path: str
    ) -> list[float] | None:
        try:
            samples, sample_rate = self._read_wav(audio_path)

            if samples.size == 0:
                logger.warning("Voice embedding extraction failed: empty audio")
                return None

            vector = self._make_spectral_embedding(samples)

            logger.info(
                "Voice embedding extracted: dim=%s, sample_rate=%s",
                len(vector),
                sample_rate
            )

            return vector.tolist()

        except Exception as error:
            logger.warning(
                "Voice embedding extraction failed: %s",
                error
            )
            return None

    def _read_wav(
        self,
        audio_path: str
    ) -> tuple[np.ndarray, int]:
        with wave.open(audio_path, "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_rate = wav_file.getframerate()
            sample_width = wav_file.getsampwidth()
            frames = wav_file.readframes(wav_file.getnframes())

        if sample_width == 2:
            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
            audio = audio / 32768.0
        elif sample_width == 4:
            audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32)
            audio = audio / 2147483648.0
        else:
            audio = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
            audio = (audio - 128.0) / 128.0

        if channels > 1:
            audio = audio.reshape(-1, channels).mean(axis=1)

        return audio, sample_rate

    def _make_spectral_embedding(
        self,
        audio: np.ndarray
    ) -> np.ndarray:
        audio = audio.astype(np.float32)

        audio = audio - np.mean(audio)

        max_abs = np.max(np.abs(audio))
        if max_abs > 0:
            audio = audio / max_abs

        frame_size = 1024
        hop_size = 512

        if len(audio) < frame_size:
            audio = np.pad(
                audio,
                (0, frame_size - len(audio))
            )

        frames = []

        for start in range(0, len(audio) - frame_size + 1, hop_size):
            frame = audio[start:start + frame_size]
            frame = frame * np.hanning(frame_size)
            spectrum = np.abs(np.fft.rfft(frame))
            spectrum = np.log1p(spectrum)
            frames.append(spectrum[:self.VECTOR_SIZE])

        if not frames:
            embedding = np.zeros(self.VECTOR_SIZE, dtype=np.float32)
        else:
            embedding = np.mean(frames, axis=0).astype(np.float32)

        if len(embedding) < self.VECTOR_SIZE:
            embedding = np.pad(
                embedding,
                (0, self.VECTOR_SIZE - len(embedding))
            )

        embedding = embedding[:self.VECTOR_SIZE]

        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding.astype(np.float32)