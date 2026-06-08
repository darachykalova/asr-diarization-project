class AlignmentService:
    """
    Service for aligning ASR words with speaker labels.

    Current version is a placeholder:
    it does not use LLM yet and does not change the text.
    It only prepares the final segment structure.

    Later this service will be replaced with LLM-based alignment.
    """

    def align(self, segments: list[dict]) -> list[dict]:
        """
        Aligns ASR segments with speaker information.

        Parameters:
            segments (list[dict]): Segments after diarization.

        Returns:
            list[dict]: Final aligned transcript segments.
        """
        aligned_segments = []

        for index, segment in enumerate(segments):
            aligned_segment = {
                "id": index,
                "start": segment["start"],
                "end": segment["end"],
                "speaker": segment["speaker"],
                "overlap": False,
                "text": segment["text"],
                "words": segment["words"],
                "alignment_source": "placeholder"
            }

            aligned_segments.append(aligned_segment)

        return aligned_segments