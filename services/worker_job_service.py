import json
from pathlib import Path
from uuid import uuid4

from services.pipeline_service import PipelineService
from services.job_service import JobService
from services.logging_service import setup_logger
from services.qdrant_service import QdrantService


class WorkerJobService:
    """
    Service that runs one audio processing worker job.

    Qdrant is optional:
    if Qdrant fails, the main ASR pipeline still finishes successfully.
    """

    def __init__(
        self,
        model_size: str = "base",
        language: str = "ru",
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
        job_status_json: str,
        job_id: str | None = None
    ):
        if job_id is None:
            job_id = f"job_{uuid4().hex}"

        input_audio_path = Path(input_audio)
        normalized_audio_path = Path(normalized_audio)
        output_json_path = Path(output_json)
        job_status_path = Path(job_status_json)

        self.logger.info(f"Job created: {job_id}")
        self.logger.info(f"Input audio: {input_audio_path}")

        job_service = JobService(status_file=str(job_status_path))

        job_service.update_status(
            job_id=job_id,
            status="queued"
        )

        self.logger.info(f"Job {job_id} status changed to queued")

        print(f"Job ID: {job_id}")
        print("Status: queued")
        print()

        job_service.update_status(
            job_id=job_id,
            status="processing"
        )

        self.logger.info(f"Job {job_id} status changed to processing")

        print("Status: processing")
        print()

        pipeline_service = PipelineService(
            model_size=self.model_size,
            language=self.language
        )

        self.logger.info(f"Job {job_id} pipeline started")

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
            job_service.update_status(
                job_id=job_id,
                status="failed",
                error=run_result.error
            )

            self.logger.error(f"Job {job_id} failed: {run_result.error}")
            self.logger.info(f"Error result saved to: {output_json_path}")
            self.logger.info(f"Job status saved to: {job_status_path}")

            return run_result

        self._save_segments_to_qdrant_safely(
            job_id=job_id,
            run_result=run_result
        )

        job_service.update_status(
            job_id=job_id,
            status="done"
        )

        self.logger.info(f"Job {job_id} status changed to done")
        self.logger.info(f"Transcript result saved to: {output_json_path}")
        self.logger.info(f"Job status saved to: {job_status_path}")

        return run_result

    def _save_segments_to_qdrant_safely(
        self,
        job_id: str,
        run_result
    ) -> None:
        """
        Saves transcript segments to Qdrant.

        This is optional.
        If Qdrant fails, the main pipeline must not fail.
        """
        try:
            if run_result.transcript is None:
                self.logger.warning(
                    f"Job {job_id} has no transcript for Qdrant saving"
                )
                return

            qdrant_service = QdrantService()

            qdrant_saved = qdrant_service.save_segments(
                job_id=job_id,
                segments=run_result.transcript.segments
            )

            if qdrant_saved:
                self.logger.info(
                    f"Job {job_id} segments saved to Qdrant"
                )
            else:
                self.logger.warning(
                    f"Job {job_id} segments were not saved to Qdrant"
                )

        except Exception as error:
            self.logger.warning(
                f"Job {job_id} Qdrant optional save failed: {error}"
            )

    def _save_result_json(
        self,
        data: dict,
        output_json: Path
    ) -> None:
        """
        Saves pipeline result to JSON file.
        """
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