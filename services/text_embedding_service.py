import logging

from sentence_transformers import SentenceTransformer


logger = logging.getLogger(__name__)


class TextEmbeddingService:
    """
    Singleton text embedding service.

    The model is loaded only once per Python process.
    This prevents repeated loading inside Celery worker.
    """

    MODEL_NAME = (
        "sentence-transformers/"
        "paraphrase-multilingual-mpnet-base-v2"
    )

    _model = None

    def __init__(self):
        if TextEmbeddingService._model is None:
            from services.model_registry import ensure_model
            # Fail fast if the model is not present locally (offline mode).
            ensure_model("sentence-transformers")
            logger.info(
                "Loading SentenceTransformer model from %s",
                self.MODEL_NAME
            )

            TextEmbeddingService._model = SentenceTransformer(
                self.MODEL_NAME
            )

        self.model = TextEmbeddingService._model

    def embed_text(
        self,
        text: str
    ) -> list[float]:
        vector = self.model.encode(
            text,
            normalize_embeddings=True
        )

        return vector.tolist()

    def embedding_dimension(
        self
    ) -> int:
        return self.model.get_embedding_dimension()
