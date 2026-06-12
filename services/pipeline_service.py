from pathlib import Path
from uuid import uuid4

from services.audio_service import normalize_audio
from services.asr_service import ASRService
from services.vad_service import VADService
from services.diarization_service import DiarizationService
from services.alignment_service import AlignmentService
from services.embedding_service import EmbeddingService
from services.timing import measure_time
from schemas.transcript_schema import TranscriptResult, PipelineRunResult


class PipelineService:
    """
    Main audio processing pipeline service.

    Pipeline steps:
    1. ffmpeg normalization
    2. VAD
    3. ASR
    4. real diarization with pyannote.audio
    5. alignment
    6. speaker embeddings
    """

    def __init__(self, model_size: str = "base", language: str | None = None):
        self.language = language

        self.vad_service = VADService()
        self.asr_service = ASRService(model_size=model_size)
        self.diarization_service = DiarizationService()
        self.alignment_service = AlignmentService()
        self.embedding_service = EmbeddingService()

    def process_audio(
        self,
        input_audio: str,
        normalized_audio: str,
        job_id: str | None = None
    ) -> PipelineRunResult:
        if job_id is None:
            job_id = f"job_{uuid4().hex}"

        try:
            transcript_result = self._run_pipeline(
                input_audio=input_audio,
                normalized_audio=normalized_audio
            )

            return PipelineRunResult(
                job_id=job_id,
                status="done",
                success=True,
                transcript=transcript_result,
                error=None
            )

        except Exception as error:
            return PipelineRunResult(
                job_id=job_id,
                status="failed",
                success=False,
                transcript=None,
                error=str(error)
            )

    @measure_time("full_pipeline")
    def _run_pipeline(
        self,
        input_audio: str,
        normalized_audio: str
    ) -> TranscriptResult:
        input_audio_path = Path(input_audio)

        normalized_file = normalize_audio(
            input_path=str(input_audio_path),
            output_path=normalized_audio
        )

        speech_segments = self.vad_service.detect_speech(normalized_file)

        asr_segments = self.asr_service.transcribe(
            audio_path=normalized_file,
            language=self.language
        )

        speaker_segments = self.diarization_service.diarize(
            audio_path=normalized_file,
            speech_segments=speech_segments
        )

        diarized_segments = self.diarization_service.assign_speakers_to_asr_segments(
            asr_segments=asr_segments,
            speaker_segments=speaker_segments
        )

        aligned_segments = self.alignment_service.align(
            segments=diarized_segments
        )

        speaker_embeddings = self.embedding_service.extract_speaker_embeddings(
            speaker_segments=speaker_segments,
            audio_path=normalized_file
        )

        transcript_result = TranscriptResult(
            input_audio=str(input_audio_path),
            normalized_audio=normalized_file,
            speech_segments=speech_segments,
            speaker_segments=speaker_segments,
            speaker_embeddings=speaker_embeddings,
            segments=aligned_segments,
            full_text=" ".join(
                segment["text"]
                for segment in aligned_segments
            )
        )

        return transcript_result