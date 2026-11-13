from pathlib import Path
from unittest.mock import MagicMock

from streamlit.testing.v1 import AppTest

import extract
import load
import psycopg2
import transform


def test_pipeline_retries_after_failure_and_caches_success(monkeypatch):
    extract_data = MagicMock(side_effect=[RuntimeError("API unavailable"), [{"id": "1"}]])
    transform_data = MagicMock(return_value=({"respondents": []}, {"received": 1}))
    load_data = MagicMock()
    connection = MagicMock()
    monkeypatch.setattr(extract, "extract_data", extract_data)
    monkeypatch.setattr(transform, "transform", transform_data)
    monkeypatch.setattr(transform, "format_summary", lambda stats: ["received from API: 1 row"])
    monkeypatch.setattr(load, "load_tables", load_data)
    monkeypatch.setattr(psycopg2, "connect", MagicMock(return_value=connection))
    for name in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        monkeypatch.setenv(name, "test")

    app = AppTest.from_file(Path(__file__).resolve().parent.parent / "streamlit_app.py").run()
    assert "API unavailable" in app.error[0].value
    assert load_data.call_count == 0

    app.run()
    assert not app.error
    assert app.success[0].value == "Data loaded successfully."
    assert extract_data.call_count == 2
    transform_data.assert_called_once_with([{"id": "1"}])
    load_data.assert_called_once_with(connection, {"respondents": []})

    app.run()
    assert extract_data.call_count == 2
    assert load_data.call_count == 1
