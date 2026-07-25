"""Typed access to config.yaml. Import this instead of hardcoding paths."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(path: str | Path | None = None) -> dict:
    p = Path(path) if path else ROOT / "config" / "config.yaml"
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


CFG = load()


def data_path(*parts) -> Path:
    return ROOT.joinpath(*parts)