class DiarizationService:
    """
    Service for speaker diarization.

    Current version is a placeholder:
    it assigns all speech to one speaker: SPEAKER_00.

    Later this service will be replaced with real diarization
    using pyannote.audio or NVIDIA NeMo.
    """

    def diarize(self, speech_segments: list[dict]) -> list[dict]:
        """
        Assigns speaker labels to speech segments.

        Parameters:
            speech_segments (list[dict]): List of speech segments from VAD.

        Returns:
            list[dict]: List of speaker segments.
        """
        speaker_segments = []

        for segment in speech_segments:
            speaker_segments.append({
                "start": segment["start"],
                "end": segment["end"],
                "speaker": "SPEAKER_00"
            })

        return speaker_segments

    def assign_speakers_to_asr_segments(
        self,
        asr_segments: list[dict],
        speaker_segments: list[dict]
    ) -> list[dict]:
        """
        Assigns speaker labels to ASR segments.

        Current simple logic:
        every ASR segment gets SPEAKER_00.

        Parameters:
            asr_segments (list[dict]): ASR text segments.
            speaker_segments (list[dict]): Diarization speaker segments.

        Returns:
            list[dict]: ASR segments with speaker labels.
        """
        if not speaker_segments:
            return asr_segments

        default_speaker = speaker_segments[0]["speaker"]

        result = []

        for segment in asr_segments:
            segment_with_speaker = {
                "start": segment["start"],
                "end": segment["end"],
                "speaker": default_speaker,
                "text": segment["text"],
                "words": segment["words"]
            }

            result.append(segment_with_speaker)

        return result