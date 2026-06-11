import json
from pathlib import Path
from uuid import uuid4

from services.pipeline_service import PipelineService
from services.logging_service import setup_logger
from services.qdrant_service import QdrantService


class WorkerJobService:
    """
    Service that runs one audio processing worker job.

    Important:
    Job status is not saved to job_status.json anymore.
    Task status is managed by Celery backend.

    Qdrant is optional:
    if Qdrant fails, the main ASR pipeline still finishes successfully.
    """

    def __init__(
        self,
        model_size: str = "base",
        language: str | None = None,
        log_file: str = "data/output/pipeline.log"
    ):
        self.model_size = model_size
        self.language = language
        self.logger = setup_logger(log_file=log_file)

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

        self._save_segments_to_qdrant_safely(
            job_id=job_id,
            run_result=run_result
        )

        self.logger.info("Job %s finished successfully", job_id)
        self.logger.info("Transcript result saved to: %s", output_json_path)

        return run_result

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