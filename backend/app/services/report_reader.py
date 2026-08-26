from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


@dataclass
class ReportReadResult:
    source_kind: str
    source_paths: list[str]
    content: str
    metadata: dict

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


class ReportReader:
    """Read-only adapter for a separately owned Hermes Profile workspace."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _safe_child(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if self.root not in path.parents:
            raise ValueError("报告来源路径越界")
        return path

    def read_week(self, week_start: date, week_end: date) -> ReportReadResult:
        markdown_files = self._weekly_markdown_files(week_start, week_end)
        if markdown_files:
            content = "\n\n".join(f"# 来源：{item.name}\n{item.read_text(encoding='utf-8', errors='replace')}" for item in markdown_files)
            return ReportReadResult("markdown", [str(item) for item in markdown_files], content[:80000], self._weekly_metadata(week_start, week_end))
        daily_dir = self._safe_child("daily_reports")
        entries, source_paths = [], []
        for offset in range((week_end - week_start).days + 1):
            current = week_start + timedelta(days=offset)
            item = daily_dir / f"{current.isoformat()}.json"
            if not item.is_file():
                continue
            try:
                payload = json.loads(item.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            entries.append((current.isoformat(), payload.get("reports", payload) if isinstance(payload, dict) else payload))
            source_paths.append(str(item))
        content = "\n\n".join(f"# 日报 {item_date}\n{json.dumps(payload, ensure_ascii=False, indent=2)}" for item_date, payload in entries)
        return ReportReadResult("daily_json", source_paths, content[:80000], self._weekly_metadata(week_start, week_end) | {"daily_report_files": len(source_paths)})

    def _weekly_markdown_files(self, week_start: date, week_end: date) -> list[Path]:
        candidates: list[Path] = []
        for folder_name in ("weekly_reports", "weekly", "reports"):
            folder = self._safe_child(folder_name)
            if folder.is_dir():
                candidates.extend(path for path in folder.rglob("*.md") if path.is_file())
        tokens = {week_start.isoformat(), week_end.isoformat(), week_start.strftime("%Y%m%d"), week_end.strftime("%Y%m%d")}
        return [path for path in candidates if any(token in path.name for token in tokens)]

    def _weekly_metadata(self, week_start: date, week_end: date) -> dict:
        folder = self._safe_child("weekly_pipeline_runs")
        if not folder.is_dir():
            return {}
        matched = []
        for item in folder.glob("*.json"):
            try:
                payload = json.loads(item.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            period = str(payload.get("period", ""))
            if week_start.isoformat() in period or week_end.isoformat() in period:
                matched.append({"file": item.name, "status": payload.get("status"), "report_count": payload.get("report_count"), "coverage": payload.get("coverage", [])})
        return {"weekly_pipeline_runs": matched}
