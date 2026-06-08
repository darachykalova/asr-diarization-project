import argparse

from services.worker_job_service import WorkerJobService


def parse_arguments():
    """
    Parses command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Local audio processing worker pipeline"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to input audio file"
    )

    parser.add_argument(
        "--normalized",
        default="data/normalized/audio_16k_mono.wav",
        help="Path where normalized audio will be saved"
    )

    parser.add_argument(
        "--output",
        default="data/output/transcript.json",
        help="Path where transcript JSON will be saved"
    )

    parser.add_argument(
        "--job-status",
        default="data/output/job_status.json",
        help="Path where job status JSON will be saved"
    )

    parser.add_argument(
        "--log-file",
        default="data/output/pipeline.log",
        help="Path where pipeline log will be saved"
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

    return parser.parse_args()


def print_transcript_result(transcript_result) -> None:
    """
    Prints short transcript result to console.
    """
    print("Speech segments:")
    for speech_segment in transcript_result.speech_segments:
        print(f"[{speech_segment.start} - {speech_segment.end}] speech")

    print()
    print("Speaker segments:")
    for speaker_segment in transcript_result.speaker_segments:
        print(
            f"[{speaker_segment.start} - {speaker_segment.end}] "
            f"{speaker_segment.speaker}"
        )

    print()
    print("Speaker embeddings:")
    for embedding in transcript_result.speaker_embeddings:
        print(
            f"{embedding.speaker}: "
            f"{embedding.embedding_source}, "
            f"vector_dim={embedding.vector_dim}"
        )

    print()
    print("Aligned transcript segments:")
    for segment in transcript_result.segments:
        print(
            f"[{segment.start} - {segment.end}] "
            f"{segment.speaker}: {segment.text}"
        )


def main():
    args = parse_arguments()

    worker_job_service = WorkerJobService(
        model_size=args.model_size,
        language=args.language,
        log_file=args.log_file
    )

    run_result = worker_job_service.run_job(
        input_audio=args.input,
        normalized_audio=args.normalized,
        output_json=args.output,
        job_status_json=args.job_status
    )

    print(f"Status: {run_result.status}")

    if not run_result.success:
        print("Pipeline failed")
        print(f"Error: {run_result.error}")
        print()
        print(f"Error result saved to: {args.output}")
        print(f"Job status saved to: {args.job_status}")
        return

    print()
    print_transcript_result(run_result.transcript)

    print()
    print(f"Result saved to: {args.output}")
    print(f"Job status saved to: {args.job_status}")


if __name__ == "__main__":
    main()