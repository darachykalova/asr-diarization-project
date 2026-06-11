class AlignmentService:
    """
    Service for aligning ASR words with speaker labels.

    Current version is a placeholder:
    it does not use LLM yet and does not change the text.
    It only prepares the final segment structure.

    Speaker labels are produced by diarization service.
    alignment_source shows that word/text alignment is still placeholder.
    diarization_source shows which diarization engine assigned the speaker.
    """

    ALIGNMENT_SOURCE = "placeholder"

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
                "overlap": segment.get("overlap", False),
                "text": segment["text"],
                "words": segment["words"],
                "alignment_source": self.ALIGNMENT_SOURCE,
                "diarization_source": segment.get(
                    "diarization_source",
                    "unknown"
                )
            }

            aligned_segments.append(aligned_segment)

        return aligned_segments