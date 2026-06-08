import json
from datetime import datetime
from pathlib import Path


class JobService:
    """
    Service for storing job status.

    Current version stores job state in a local JSON file.
    Later this logic will be replaced with PostgreSQL.
    """

    def __init__(self, status_file: str):
        """
        Initializes job service.

        Parameters:
            status_file (str): Path to JSON file where job status will be saved.
        """
        self.status_file = Path(status_file)

    def update_status(
        self,
        job_id: str,
        status: str,
        error: str | None = None
    ) -> None:
        """
        Updates job status.

        Parameters:
            job_id (str): Job identifier.
            status (str): Job status: queued, processing, done, failed.
            error (str | None): Error message if job failed.
        """
        self.status_file.parent.mkdir(parents=True, exist_ok=True)

        job_data = {
            "job_id": job_id,
            "status": status,
            "error": error,
            "updated_at": datetime.now().isoformat(timespec="seconds")
        }

        with open(self.status_file, "w", encoding="utf-8") as file:
            json.dump(job_data, file, ensure_ascii=False, indent=4)

    def load_status(self) -> dict | None:
        """
        Loads current job status from JSON file.

        Returns:
            dict | None: Job status data or None if file does not exist.
        """
        if not self.status_file.exists():
            return None

        with open(self.status_file, "r", encoding="utf-8") as file:
            return json.load(file)