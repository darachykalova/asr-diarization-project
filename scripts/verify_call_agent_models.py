"""
Pre-flight model verification for the call-agent service.

Checks that the Vosk ASR model and Silero TTS model are present on the
local models volume before the service starts.

- All present  -> prints an OK table, exits 0.
- Any missing  -> prints which models are missing + how to get them, exits 1.

Run automatically at startup (see call_agent/main.py _check_call_agent_models),
or manually:

    docker compose exec call-agent python scripts/verify_call_agent_models.py
"""

import sys
from pathlib import Path

# Ensure project root is importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from call_agent.config import get_settings  # noqa: E402

settings = get_settings()


def _check_vosk(path: Path) -> tuple[bool, str]:
    """Returns (present, message)."""
    if not path.exists():
        return False, f"Directory does not exist: {path}"
    if not path.is_dir():
        return False, f"Path exists but is not a directory: {path}"
    # Vosk models always contain final.mdl as a marker file
    marker = path / "final.mdl"
    if not marker.exists():
        return False, f"Directory exists but final.mdl is missing: {path}"
    return True, str(path)


def _check_silero(path: Path) -> tuple[bool, str]:
    """Returns (present, message)."""
    if not path.exists():
        return False, f"File does not exist: {path}"
    if not path.is_file():
        return False, f"Path exists but is not a file: {path}"
    return True, str(path)


def main() -> None:
    vosk_path = Path(settings.vosk_model_path)
    silero_path = Path(settings.silero_model_path)

    checks = [
        {
            "name": "Vosk ASR model (Russian)",
            "used_for": "Real-time speech recognition (StreamingASR)",
            "path": vosk_path,
            "result": _check_vosk(vosk_path),
            "how_to_get": (
                "wget https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip\n"
                "          unzip vosk-model-small-ru-0.22.zip\n"
                f"          mv vosk-model-small-ru-0.22 {vosk_path}"
            ),
        },
        {
            "name": "Silero TTS model (v4 Russian)",
            "used_for": "Text-to-speech synthesis for agent replies",
            "path": silero_path,
            "result": _check_silero(silero_path),
            "how_to_get": (
                "python -c \""
                "import torch; "
                "torch.hub.download_url_to_file("
                "'https://models.silero.ai/models/tts/ru/v4_ru.pt', "
                f"'{silero_path}')\""
            ),
        },
    ]

    print("=" * 70)
    print("Call-agent model verification")
    print("=" * 70)

    missing = []
    for spec in checks:
        present, detail = spec["result"]
        status = "OK     " if present else "MISSING"
        print(f"[{status}] {spec['name']}")
        print(f"          used for: {spec['used_for']}")
        print(f"          path:     {spec['path']}")
        if not present:
            print(f"          error:    {detail}")
            print(f"          get it:   {spec['how_to_get']}")
            missing.append(spec["name"])

    print("=" * 70)

    if missing:
        print(f"FAILED: {len(missing)} of {len(checks)} models missing.")
        print("The call-agent will not start until these are present locally.")
        print("=" * 70)
        sys.exit(1)

    print(f"PASSED: all {len(checks)} models present. Call-agent can run offline.")
    print("=" * 70)
    sys.exit(0)


if __name__ == "__main__":
    main()
