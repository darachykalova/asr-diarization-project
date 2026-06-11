import os
from pathlib import Path

import numpy as np
import torch
from scipy.io import wavfile


class DiarizationService:
    """
    Real speaker diarization using pyannote.audio.

    Audio is loaded with scipy, not torchcodec.
    HF_TOKEN must be set in environment variables.
    """

    DIARIZATION_SOURCE = "pyannote"
    MODEL_NAME = "pyannote/speaker-diarization-3.1"

    def __init__(self):
        self.pipeline = None

    def _load_pipeline(self):
        if self.pipeline is not None:
            return self.pipeline

        hf_token = os.getenv("HF_TOKEN")

        if not hf_token:
            raise RuntimeError(
                "HF_TOKEN is not set. "
                "Set Hugging Face token before running diarization."
            )

        from pyannote.audio import Pipeline

        self.pipeline = Pipeline.from_pretrained(
            self.MODEL_NAME,
            token=hf_token
        )

        device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.pipeline.to(device)

        return self.pipeline

    def _load_audio_without_torchcodec(
        self,
        audio_path: str
    ) -> tuple[torch.Tensor, int]:
        sample_rate, audio = wavfile.read(audio_path)

        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.int32:
            audio = audio.astype(np.float32) / 2147483648.0
        elif audio.dtype == np.uint8:
            audio = (audio.astype(np.float32) - 128.0) / 128.0
        else:
            audio = audio.astype(np.float32)

        if audio.ndim == 1:
            audio = np.expand_dims(audio, axis=0)
        else:
            audio = audio.T

        waveform = torch.from_numpy(audio)

        return waveform, int(sample_rate)

    def diarize(
        self,
        audio_path: str,
        speech_segments: list[dict] | None = None
    ) -> list[dict]:
        audio_file = Path(audio_path)

        if not audio_file.exists():
            raise FileNotFoundError(
                f"Audio file not found: {audio_path}"
            )

        pipeline = self._load_pipeline()

        waveform, sample_rate = self._load_audio_without_torchcodec(
            str(audio_file)
        )

        device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        waveform = waveform.to(device)

        diarization_result = pipeline(
            {
                "waveform": waveform,
                "sample_rate": sample_rate
            },
            min_speakers=1,
            max_speakers=2
        )

        if hasattr(diarization_result, "speaker_diarization"):
            diarization_annotation = diarization_result.speaker_diarization
        else:
            diarization_annotation = diarization_result

        speaker_segments = []

        for turn, _, speaker in diarization_annotation.itertracks(
            yield_label=True
        ):
            speaker_segments.append(
                {
                    "start": round(float(turn.start), 3),
                    "end": round(float(turn.end), 3),
                    "speaker": str(speaker),
                    "diarization_source": self.DIARIZATION_SOURCE
                }
            )

        speaker_segments.sort(
            key=lambda item: item["start"]
        )

        return speaker_segments

    def assign_speakers_to_asr_segments(
        self,
        asr_segments: list[dict],
        speaker_segments: list[dict]
    ) -> list[dict]:
        result = []

        for asr_segment in asr_segments:
            best_speaker = "UNKNOWN"
            best_overlap = 0.0
            best_source = self.DIARIZATION_SOURCE

            asr_start = float(asr_segment["start"])
            asr_end = float(asr_segment["end"])

            for speaker_segment in speaker_segments:
                speaker_start = float(speaker_segment["start"])
                speaker_end = float(speaker_segment["end"])

                overlap_start = max(
                    asr_start,
                    speaker_start
                )

                overlap_end = min(
                    asr_end,
                    speaker_end
                )

                overlap = max(
                    0.0,
                    overlap_end - overlap_start
                )

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = speaker_segment["speaker"]
                    best_source = speaker_segment.get(
                        "diarization_source",
                        self.DIARIZATION_SOURCE
                    )

            result.append(
                {
                    "start": asr_segment["start"],
                    "end": asr_segment["end"],
                    "speaker": best_speaker,
                    "text": asr_segment["text"],
                    "words": asr_segment["words"],
                    "diarization_source": best_source
                }
            )

        return result