import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "unassisted_cube_baseline", Path(__file__).parents[2] / "examples/complete-journey/evals/cube_baseline.py"
)
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


async def test_generic_export_saves_cube_rows_without_analysis(monkeypatch, tmp_path):
    async def request(path, params):
        assert path == "/load"
        return {"data": [{"test.value": 1}, {"test.value": 2}]}

    monkeypatch.setattr(baseline, "request", request)
    monkeypatch.setenv("BENCH_EXPORT_DIR", str(tmp_path))
    result = await baseline.export_query_csv({"measures": ["test.value"], "limit": 10})
    assert result["rows"] == 2 and result["retrieval_complete"] is True
    assert Path(result["path"]).read_text().splitlines() == ["test.value", "1", "2"]
    assert not hasattr(baseline, "campaign_8_ols")


async def test_export_refuses_explicit_or_truncated_limit(monkeypatch, tmp_path):
    async def request(path, params):
        return {"data": [{"test.value": 1}] * 50000}

    monkeypatch.setattr(baseline, "request", request)
    monkeypatch.setenv("BENCH_EXPORT_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="offset"):
        await baseline.export_query_csv({"offset": 1})
    with pytest.raises(ValueError, match="single-page"):
        await baseline.export_query_csv({"measures": ["test.value"]})
    assert list(tmp_path.iterdir()) == []
