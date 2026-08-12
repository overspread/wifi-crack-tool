"""Privacy-preserving local audit logging for offline training events."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


class AuditLogger:
    """Write explicit, local-only JSONL audit records.

    Records are intentionally limited to simulated-event metadata. Password values,
    network adapter names, BSSIDs, and packet content are never accepted or stored.
    """

    def __init__(self, directory: str | Path = "audit_logs") -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "wifi_defense_audit.jsonl"

    def record(self, event: str, profile: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        """Append one structured local audit event and return the saved record."""
        safe_details = details or {}
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": str(event),
            "profile": str(profile)[:64],
            "details": safe_details,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def read_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return the newest local audit records, newest first."""
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
        records: list[dict[str, Any]] = []
        for line in reversed(lines[-max(1, limit):]):
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records
