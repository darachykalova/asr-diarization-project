import json
from pathlib import Path
from uuid import uuid4

from database import crud
from database.repository import TranscriptRepository
from database.session import SessionLocal
from services.audio_segment_extractor import extract_longest_segment
from services.logging_service import setup_logger
from services.pipeline_service import PipelineService
from services.qdrant_service import QdrantService
from services.speaker_identification_service import SpeakerIdentificationService
from services.voice_embedding_service import VoiceEmbeddingService


class WorkerJobService:
    def __init__(
        self,
        model_size: str = "base",
        language: str | None = None,
        log_file: str = "data/output/pipeline.log"
    ):
        self.model_size = model_size
        self.language = language
        self.logger = setup_logger(log_file=log_file)
        self.transcript_repository = TranscriptRepository()

    def run_job(
        self,
        input_audio: str,
        normalized_audio: str,
        output_json: str,
        job_id: str | None = None
    ):
        if job_id is None:
            job_id = f"job_{uuid4().hex}"

        input_audio_path = Path(input_audio)
        normalized_audio_path = Path(normalized_audio)
        output_json_path = Path(output_json)

        self.logger.info("Job created: %s", job_id)
        self.logger.info("Input audio: %s", input_audio_path)
        self.logger.info("Job %s processing started", job_id)

        pipeline_service = PipelineService(
            model_size=self.model_size,
            language=self.language
        )

        self.logger.info("Job %s pipeline started", job_id)

        run_result = pipeline_service.process_audio(
            input_audio=str(input_audio_path),
            normalized_audio=str(normalized_audio_path),
            job_id=job_id
        )

        self._save_result_json(
            data=run_result.model_dump(),
            output_json=output_json_path
        )

        if not run_result.success:
            self.logger.error("Job %s failed: %s", job_id, run_result.error)
            self.logger.info("Error result saved to: %s", output_json_path)
            return run_result

        transcript_id = self._save_transcript_to_postgres_safely(
            job_id=job_id,
            run_result=run_result
        )

        if transcript_id is not None:
            self._identify_speakers_safely(
                job_id=job_id,
                transcript_id=transcript_id,
                normalized_audio=str(normalized_audio_path),
                run_result=run_result
            )

        self._save_segments_to_qdrant_safely(
            job_id=job_id,
            run_result=run_result
        )

        self.logger.info("Job %s finished successfully", job_id)
        self.logger.info("Transcript result saved to: %s", output_json_path)

        return run_result

    def _save_transcript_to_postgres_safely(
        self,
        job_id: str,
        run_result
    ) -> int | None:
        try:
            transcript_id = self.transcript_repository.save_pipeline_result(
                run_result=run_result
            )

            self.logger.info(
                "Job %s transcript saved to Postgres with transcript_id=%s",
                job_id,
                transcript_id
            )

            return transcript_id

        except Exception as error:
            self.logger.warning(
                "Job %s Postgres optional save failed: %s",
                job_id,
                error
            )
            return None

    def _identify_speakers_safely(
        self,
        job_id: str,
        transcript_id: int,
        normalized_audio: str,
        run_result
    ) -> None:
        try:
            if run_result.transcript is None:
                return

            speaker_segments = self._build_speaker_segments(run_result)

            if not speaker_segments:
                self.logger.warning(
                    "Job %s has no speaker segments for voice matching",
                    job_id
                )
                return

            labels = sorted({
                segment["speaker"]
                for segment in speaker_segments
                if segment.get("speaker")
            })

            if not labels:
                return

            voice_service = VoiceEmbeddingService()

            if not voice_service.is_available():
                self.logger.warning(
                    "Job %s: VoiceEmbeddingService unavailable, fallback to anonymous assignment",
                    job_id
                )

                self._assign_anonymous_fallback(
                    job_id=job_id,
                    transcript_id=transcript_id,
                    labels=labels
                )

                return

            identification_service = SpeakerIdentificationService()

            db = SessionLocal()

            try:
                current_job_speaker_ids: set[int] = set()

                for local_label in labels:
                    clip_path = str(
                        Path("data/temp_voice") /
                        job_id /
                        f"{local_label}.wav"
                    )

                    extracted_path = extract_longest_segment(
                        audio_path=normalized_audio,
                        segments=speaker_segments,
                        speaker_label=local_label,
                        output_path=clip_path,
                        min_duration=3.0
                    )

                    if extracted_path is None:
                        self.logger.warning(
                            "Job %s: no suitable voice segment for %s, fallback anonymous",
                            job_id,
                            local_label
                        )

                        speaker = crud.create_anonymous_speaker(
                            db=db,
                            name=f"Unknown speaker {local_label}"
                        )

                        match_score = None

                    else:
                        embedding = voice_service.extract_embedding(
                            extracted_path
                        )

                        if embedding is None:
                            self.logger.warning(
                                "Job %s: embedding failed for %s, fallback anonymous",
                                job_id,
                                local_label
                            )

                            speaker = crud.create_anonymous_speaker(
                                db=db,
                                name=f"Unknown speaker {local_label}"
                            )

                            match_score = None

                        else:
                            speaker_id, match_score = identification_service.find_speaker(
                                embedding=embedding,
                                excluded_speaker_ids=current_job_speaker_ids
                            )

                            if speaker_id is None:
                                speaker = crud.create_anonymous_speaker(
                                    db=db,
                                    name=f"Unknown speaker {local_label}"
                                )

                                identification_service.save_embedding(
                                    speaker_id=speaker.id,
                                    embedding=embedding
                                )

                                self.logger.info(
                                    "Job %s: created anonymous speaker_id=%s for %s and saved voice embedding",
                                    job_id,
                                    speaker.id,
                                    local_label
                                )

                            else:
                                speaker = crud.get_speaker(
                                    db=db,
                                    speaker_id=speaker_id
                                )

                                if speaker is None:
                                    speaker = crud.create_anonymous_speaker(
                                        db=db,
                                        name=f"Unknown speaker {local_label}"
                                    )

                                    identification_service.save_embedding(
                                        speaker_id=speaker.id,
                                        embedding=embedding
                                    )

                                    match_score = None

                                    self.logger.warning(
                                        "Job %s: Qdrant matched missing speaker_id=%s, created new speaker_id=%s",
                                        job_id,
                                        speaker_id,
                                        speaker.id
                                    )

                                else:
                                    self.logger.info(
                                        "Job %s: matched %s to speaker_id=%s score=%s",
                                        job_id,
                                        local_label,
                                        speaker.id,
                                        match_score
                                    )

                    current_job_speaker_ids.add(speaker.id)

                    crud.create_occurrence(
                        db=db,
                        speaker_id=speaker.id,
                        transcript_id=transcript_id,
                        local_label=local_label,
                        match_score=match_score
                    )

                    crud.update_segments_speaker_id(
                        db=db,
                        transcript_id=transcript_id,
                        local_label=local_label,
                        speaker_id=speaker.id
                    )

                    self.logger.info(
                        "Job %s: assigned %s to speaker_id=%s",
                        job_id,
                        local_label,
                        speaker.id
                    )

            finally:
                db.close()

        except Exception as error:
            self.logger.warning(
                "Job %s speaker identification failed: %s",
                job_id,
                error
            )

    def _assign_anonymous_fallback(
        self,
        job_id: str,
        transcript_id: int,
        labels: list[str]
    ) -> None:
        db = SessionLocal()

        try:
            for local_label in labels:
                speaker = crud.create_anonymous_speaker(
                    db=db,
                    name=f"Unknown speaker {local_label}"
                )

                crud.create_occurrence(
                    db=db,
                    speaker_id=speaker.id,
                    transcript_id=transcript_id,
                    local_label=local_label,
                    match_score=None
                )

                crud.update_segments_speaker_id(
                    db=db,
                    transcript_id=transcript_id,
                    local_label=local_label,
                    speaker_id=speaker.id
                )

                self.logger.info(
                    "Job %s: fallback assigned %s to anonymous speaker_id=%s",
                    job_id,
                    local_label,
                    speaker.id
                )

        finally:
            db.close()

    def _build_speaker_segments(
    self,
    run_result
) -> list[dict]:

     if (
        run_result.transcript is not None
        and run_result.transcript.speaker_segments
    ):
        return [
            {
                "speaker": segment.speaker,
                "start": segment.start,
                "end": segment.end
            }
            for segment in run_result.transcript.speaker_segments
        ]

     if run_result.transcript is None:
        return []

     return [
        {
            "speaker": segment.speaker,
            "start": segment.start,
            "end": segment.end
        }
        for segment in run_result.transcript.segments
    ]

    def _save_segments_to_qdrant_safely(
        self,
        job_id: str,
        run_result
    ) -> None:
        try:
            if run_result.transcript is None:
                self.logger.warning(
                    "Job %s has no transcript for Qdrant saving",
                    job_id
                )
                return

            qdrant_service = QdrantService()

            qdrant_saved = qdrant_service.save_segments(
                job_id=job_id,
                segments=run_result.transcript.segments
            )

            if qdrant_saved:
                self.logger.info(
                    "Job %s segments saved to Qdrant",
                    job_id
                )
            else:
                self.logger.warning(
                    "Job %s segments were not saved to Qdrant",
                    job_id
                )

        except Exception as error:
            self.logger.warning(
                "Job %s Qdrant optional save failed: %s",
                job_id,
                error
            )

    def _save_result_json(
        self,
        data: dict,
        output_json: Path
    ) -> None:
        output_json.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(output_json, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=4
            )