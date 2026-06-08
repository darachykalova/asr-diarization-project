import argparse
import json
from pathlib import Path


def parse_arguments():
    """
    Parses command line arguments for reading transcript.
    """
    parser = argparse.ArgumentParser(
        description="Print transcript text by job ID"
    )

    parser.add_argument(
        "--job-id",
        required=True,
        help="Job ID"
    )

    parser.add_argument(
        "--jobs-dir",
        default="data/output/jobs",
        help="Directory where job results are stored"
    )

    parser.add_argument(
        "--with-time",
        action="store_true",
        help="Print transcript with timestamps"
    )

    parser.add_argument(
        "--with-speaker",
        action="store_true",
        help="Print speaker labels"
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

    job_dir = Path(args.jobs_dir) / args.job_id
    transcript_file = job_dir / "transcript.json"

    if not job_dir.exists():
        print(f"Job not found: {args.job_id}")
        print(f"Expected directory: {job_dir}")
        return

    transcript_data = load_json(transcript_file)

    if transcript_data is None:
        print(f"Transcript file not found: {transcript_file}")
        return

    if not transcript_data.get("success"):
        print("Transcript is not available because job failed.")
        print(f"Status: {transcript_data.get('status')}")
        print(f"Error: {transcript_data.get('error')}")
        return

    transcript = transcript_data.get("transcript")
    if transcript is None:
        print("Transcript data is empty.")
        return

    segments = transcript.get("segments", [])

    print(f"Job ID: {transcript_data.get('job_id')}")
    print(f"Status: {transcript_data.get('status')}")
    print()

    for segment in segments:
        text = segment.get("text", "")

        prefix_parts = []

        if args.with_time:
            start = segment.get("start")
            end = segment.get("end")
            prefix_parts.append(f"[{start} - {end}]")

        if args.with_speaker:
            speaker = segment.get("speaker")
            prefix_parts.append(f"{speaker}:")

        if prefix_parts:
            print(" ".join(prefix_parts), text)
        else:
            print(text)


if __name__ == "__main__":
    main()