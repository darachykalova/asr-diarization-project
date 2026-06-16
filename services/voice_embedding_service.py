import logging

logger = logging.getLogger(__name__)


class VoiceEmbeddingService:
    """
    Lazy voice embedding service.

    Важно:
    SpeechBrain импортируется только при создании этого сервиса,
    а не при запуске FastAPI.
    Поэтому API startup не падает.
    """

    _model = None

    def __init__(self):
        if VoiceEmbeddingService._model is None:
            try:
                from speechbrain.inference.speaker import EncoderClassifier

                logger.info("Loading SpeechBrain speaker embedding model...")

                VoiceEmbeddingService._model = EncoderClassifier.from_hparams(
                    source="speechbrain/spkrec-ecapa-voxceleb",
                    savedir="models/speechbrain_ecapa"
                )

                logger.info("SpeechBrain speaker embedding model loaded.")

            except Exception as error:
                logger.warning(
                    "SpeechBrain model loading failed: %s",
                    error
                )

                VoiceEmbeddingService._model = None

    def is_available(self) -> bool:
        return VoiceEmbeddingService._model is not None

    def extract_embedding(
        self,
        audio_path: str
    ) -> list[float] | None:
        if VoiceEmbeddingService._model is None:
            return None

        try:
            embedding = VoiceEmbeddingService._model.encode_file(
                audio_path
            )

            return (
                embedding.squeeze()
                .detach()
                .cpu()
                .numpy()
                .tolist()
            )

        except Exception as error:
            logger.warning(
                "Voice embedding extraction failed: %s",
                error
            )

            return None