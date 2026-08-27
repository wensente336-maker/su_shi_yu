import json
from datetime import date

from app.services.report_reader import ReportReader
from app.services.analysis import build_analysis_prompt


def test_reads_daily_json_when_weekly_markdown_is_missing(tmp_path):
    reports = tmp_path / "daily_reports"
    reports.mkdir()
    (tmp_path / "weekly_pipeline_runs").mkdir()
    (reports / "2026-08-24.json").write_text(json.dumps({"reports": [{"author": "张三", "content": "完成客户沟通"}]}, ensure_ascii=False), encoding="utf-8")

    result = ReportReader(str(tmp_path)).read_week(date(2026, 8, 24), date(2026, 8, 30))

    assert result.source_kind == "daily_json"
    assert len(result.source_paths) == 1
    assert "完成客户沟通" in result.content
    assert result.metadata["daily_report_files"] == 1


def test_prefers_matching_weekly_markdown(tmp_path):
    weekly = tmp_path / "weekly_reports"
    weekly.mkdir()
    (tmp_path / "daily_reports").mkdir()
    (tmp_path / "weekly_pipeline_runs").mkdir()
    (weekly / "weekly-2026-08-24.md").write_text("# 周报\n销售进展", encoding="utf-8")

    result = ReportReader(str(tmp_path)).read_week(date(2026, 8, 24), date(2026, 8, 30))

    assert result.source_kind == "markdown"
    assert "销售进展" in result.content


def test_limits_multibyte_weekly_report_by_bytes(tmp_path):
    weekly = tmp_path / "weekly_reports"
    weekly.mkdir()
    (tmp_path / "daily_reports").mkdir()
    (tmp_path / "weekly_pipeline_runs").mkdir()
    (weekly / "2026-W35.md").write_text("经营记录" * 30_000, encoding="utf-8")

    result = ReportReader(str(tmp_path)).read_week(date(2026, 8, 24), date(2026, 8, 28))

    assert len(result.content.encode("utf-8")) < 61_000
    assert "安全上限截断" in result.content


def test_analysis_prompt_has_bounded_byte_size():
    prompt = build_analysis_prompt(
        {"submissions": [{"values": {"notes": "业务" * 50_000}}]},
        "本周周报" * 50_000,
        "上周周报" * 50_000,
    )

    assert len(prompt.encode("utf-8")) < 125_000
