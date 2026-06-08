import argparse

from tasks import process_audio_task


def parse_arguments():
    """
    Parses command line arguments for sending Celery task.
    """
    parser = argparse.ArgumentParser(
        description="Send audio processing task to Celery worker"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to input audio file"
    )

    parser.add_argument(
        "--model-size",
        default="base",
        help="Whisper model size: tiny, base, small, medium, large-v3"
    )

    parser.add_argument(
        "--language",
        default="ru",
        help="Audio language code"
    )

    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for task result"
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    result = process_audio_task.delay(
        input_audio=args.input,
        model_size=args.model_size,
        language=args.language
    )

    print("Celery task sent")
    print(f"Celery task id: {result.id}")

    if args.wait:
        print("Waiting for result...")

        task_result = result.get(timeout=300)

        print("Task finished")
        print(f"Job ID: {task_result.get('job_id')}")
        print(f"Status: {task_result.get('status')}")
        print(f"Success: {task_result.get('success')}")

        if not task_result.get("success"):
            print(f"Error: {task_result.get('error')}")
            return

        job_id = task_result.get("job_id")
        print()
        print(f"Transcript saved to: data/output/jobs/{job_id}/transcript.json")
        print(f"Job status saved to: data/output/jobs/{job_id}/job_status.json")
        print(f"Log saved to: data/output/jobs/{job_id}/pipeline.log")


if __name__ == "__main__":
    main()