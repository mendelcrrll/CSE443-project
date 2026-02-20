import json
from pathlib import Path
from typing import Any


class LocalStore:
    def __init__(self) -> None:
        self.path = Path(__file__).resolve().parents[1] / "data" / "store.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(
                {
                    "journal": [],
                    "definitions": [],
                    "threads": [],
                    "drafts": [],
                    "audit_logs": [],
                }
            )

    def _read(self) -> dict[str, list[dict[str, Any]]]:
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: dict[str, list[dict[str, Any]]]) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def save(self, bucket: str, item: dict[str, Any]) -> None:
        data = self._read()
        data.setdefault(bucket, [])
        data[bucket].append(item)
        self._write(data)

    def list(self, bucket: str) -> list[dict[str, Any]]:
        data = self._read()
        return data.get(bucket, [])

