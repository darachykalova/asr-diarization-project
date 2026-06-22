import logging
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

logger = logging.getLogger(__name__)


class _PartialResultError(Exception):
    def __init__(self, transcript: TranscriptResult, reason: str):
        super().__init__(reason)
        self.transcript = transcript
        self.reason = reason


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

    def __init__(
        self,
        model_size: str = "base",
        language: str | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        initial_prompt: str | None = None,
        on_progress=None,
    ):
        self.language = language
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self.initial_prompt = initial_prompt
        self._on_progress = on_progress  # callable(progress: int)

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

        except _PartialResultError as exc:
            return PipelineRunResult(
                job_id=job_id,
                status="partial",
                success=True,
                transcript=exc.transcript,
                error=exc.reason
            )

        except Exception as error:
            return PipelineRunResult(
                job_id=job_id,
                status="failed",
                success=False,
                transcript=None,
                error=str(error)
            )

    def _report(self, progress: int) -> None:
        if self._on_progress is not None:
            try:
                self._on_progress(progress)
            except Exception:
                pass

    @measure_time("full_pipeline")
    def _run_pipeline(
        self,
        input_audio: str,
        normalized_audio: str
    ) -> TranscriptResult:
        input_audio_path = Path(input_audio)

        self._report(10)
        normalized_file = normalize_audio(
            input_path=str(input_audio_path),
            output_path=normalized_audio
        )

        self._report(20)
        speech_segments = self.vad_service.detect_speech(normalized_file)

        self._report(35)
        asr_segments, detected_language, duration_sec = self.asr_service.transcribe(
            audio_path=normalized_file,
            language=self.language,
            initial_prompt=self.initial_prompt,
        )

        diarization_error: str | None = None
        speaker_segments = []

        try:
            self._report(60)
            speaker_segments = self.diarization_service.diarize(
                audio_path=normalized_file,
                speech_segments=speech_segments,
                min_speakers=self.min_speakers,
                max_speakers=self.max_speakers,
            )
        except Exception as exc:
            diarization_error = f"diarization failed: {exc}"
            logger.warning("Diarization failed, continuing without speaker labels: %s", exc)

        self._report(75)
        diarized_segments = self.diarization_service.assign_speakers_to_asr_segments(
            asr_segments=asr_segments,
            speaker_segments=speaker_segments
        )

        self._report(85)
        aligned_segments = self.alignment_service.align(segments=diarized_segments)

        self._report(92)
        try:
            speaker_embeddings = self.embedding_service.extract_speaker_embeddings(
                speaker_segments=speaker_segments,
                audio_path=normalized_file
            )
        except Exception as exc:
            logger.warning("Embedding extraction failed: %s", exc)
            speaker_embeddings = []

        transcript_result = TranscriptResult(
            input_audio=str(input_audio_path),
            normalized_audio=normalized_file,
            speech_segments=speech_segments,
            speaker_segments=speaker_segments,
            speaker_embeddings=speaker_embeddings,
            segments=aligned_segments,
            full_text=" ".join(segment["text"] for segment in aligned_segments),
            language=self.language or detected_language,
            duration_sec=duration_sec,
        )

        if diarization_error:
            raise _PartialResultError(transcript=transcript_result, reason=diarization_error)

        return transcript_result