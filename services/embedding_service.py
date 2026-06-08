class EmbeddingService:
    """
    Service for extracting speaker voice embeddings.

    Current version is a placeholder:
    it does not extract real voice vectors yet.

    Later this service will be replaced with real embeddings
    using pyannote, SpeechBrain, or NVIDIA NeMo.
    """

    def extract_speaker_embeddings(
        self,
        speaker_segments: list[dict],
        audio_path: str
    ) -> list[dict]:
        """
        Creates placeholder speaker embeddings.

        Parameters:
            speaker_segments (list[dict]): Speaker segments from diarization.
            audio_path (str): Path to normalized audio file.

        Returns:
            list[dict]: List of speaker embedding metadata.
        """
        unique_speakers = set()

        for segment in speaker_segments:
            unique_speakers.add(segment["speaker"])

        embeddings = []

        for speaker in sorted(unique_speakers):
            embeddings.append({
                "speaker": speaker,
                "audio_path": audio_path,
                "embedding_source": "placeholder",
                "vector": [],
                "vector_dim": 0
            })

        return embeddings