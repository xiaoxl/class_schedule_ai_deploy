"""Shared application release version, maintained in the root VERSION file."""

from pathlib import Path


APP_VERSION_FILE = Path(__file__).resolve().parents[2] / "VERSION"


def get_app_version() -> str:
    return APP_VERSION_FILE.read_text(encoding="utf-8").strip()
