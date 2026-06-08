import argparse
import json
from pathlib import Path


def parse_arguments():
    """
    Parses command line arguments for checking job status.
    """
    parser = argparse.ArgumentParser(
        description="Check audio processing job status"
    )

    parser.add_argument(
        "--job-id",
        required=True,
        help="Job ID to check"
    )

    parser.add_argument(
        "--jobs-dir",
        default="data/output/jobs",
        help="Directory where job results are stored"
    )

    return parser.parse_args()


def load_json(file_path: Path) -> dict | None:
    """
    Loads JSON file if it exists.
    """
    if not file_path.exists():
        return None

    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def main():
    args = parse_arguments()

    job_id = args.job_id
    jobs_dir = Path(args.jobs_dir)

    job_dir = jobs_dir / job_id
    job_status_file = job_dir / "job_status.json"
    transcript_file = job_dir / "transcript.json"
    log_file = job_dir / "pipeline.log"

    if not job_dir.exists():
        print(f"Job not found: {job_id}")
        print(f"Expected directory: {job_dir}")
        return

    job_status = load_json(job_status_file)

    if job_status is None:
        print(f"Job status file not found: {job_status_file}")
        return

    print(f"Job ID: {job_status.get('job_id')}")
    print(f"Status: {job_status.get('status')}")
    print(f"Error: {job_status.get('error')}")
    print(f"Updated at: {job_status.get('updated_at')}")
    print()

    if transcript_file.exists():
        print(f"Transcript: {transcript_file}")
    else:
        print("Transcript: not found")

    if log_file.exists():
        print(f"Log: {log_file}")
    else:
        print("Log: not found")


if __name__ == "__main__":
    main()