import logging
import os

import numpy as np
import soundfile as sf
import torch
import torchaudio

logger = logging.getLogger(__name__)

_MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "/app/models")


class VoiceEmbeddingService:
    VECTOR_SIZE = 192

    _model = None

    def __init__(self):
        if VoiceEmbeddingService._model is None:
            from speechbrain.inference.speaker import EncoderClassifier
            logger.info("Loading SpeechBrain ECAPA-TDNN model...")
            VoiceEmbeddingService._model = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=os.path.join(_MODEL_CACHE_DIR, "spkrec-ecapa-voxceleb"),
                run_opts={"device": "cpu"}
            )
            logger.info("SpeechBrain ECAPA-TDNN model loaded.")

    def is_available(self) -> bool:
        return True

    def extract_embedding(self, audio_path: str) -> list[float] | None:
        try:
            data, sample_rate = sf.read(audio_path, dtype="float32", always_2d=True)

            # data shape: (samples, channels) -> transpose to (channels, samples)
            signal = torch.from_numpy(data.T)

            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(
                    orig_freq=sample_rate,
                    new_freq=16000
                )
                signal = resampler(signal)

            if signal.shape[0] > 1:
                signal = signal.mean(dim=0, keepdim=True)

            with torch.no_grad():
                embeddings = VoiceEmbeddingService._model.encode_batch(signal)

            vector = embeddings.squeeze().cpu().numpy().astype(np.float32)

            norm = float(np.linalg.norm(vector))
            if norm > 0:
                vector = vector / norm

            logger.info("Voice embedding extracted: dim=%s", len(vector))
            return vector.tolist()

        except Exception as error:
            logger.warning("Voice embedding extraction failed: %s", error)
            return None
