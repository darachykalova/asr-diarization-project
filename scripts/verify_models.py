"""
Pre-flight model verification.

Checks that every required ML model is present on the local models volume.
- All present  -> prints an OK table, exits 0.
- Any missing  -> prints which models are missing + how to get them, exits 1.

Run automatically before the Celery worker starts (see docker-compose.yml) and
usable manually:

    docker compose exec worker python scripts/verify_models.py
"""

import logging
import sys

# Ensure project root is importable when run as a script.
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.model_registry import REQUIRED_MODELS, check  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("verify_models")


def main() -> None:
    print("=" * 70)
    print("ML model verification (offline readiness)")
    print("=" * 70)

    missing = []
    for spec in REQUIRED_MODELS:
        present = check(spec)
        status = "OK     " if present else "MISSING"
        print(f"[{status}] {spec.name}")
        print(f"          used for: {spec.used_for}")
        print(f"          path:     {spec.local_path}")
        if not present:
            print(f"          get it:   {spec.how_to_get}")
            missing.append(spec)

    print("=" * 70)

    if missing:
        print(f"FAILED: {len(missing)} of {len(REQUIRED_MODELS)} models missing.")
        print("The program will not start until these are present locally.")
        print("=" * 70)
        sys.exit(1)

    print(f"PASSED: all {len(REQUIRED_MODELS)} models present. Service can run offline.")
    print("=" * 70)
    sys.exit(0)


if __name__ == "__main__":
    main()
