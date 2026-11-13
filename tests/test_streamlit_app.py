from pathlib import Path
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

import streamlit_app


def test_pipeline_calls_etl_functions_and_propagates_errors(monkeypatch):
    extract_data = MagicMock(side_effect=[RuntimeError("API unavailable"), [{"id": "1"}]])
    transform_data = MagicMock(return_value=({"respondents": []}, {"received": 1}))
    load_data = MagicMock()
    connection = MagicMock()
    monkeypatch.setattr(streamlit_app, "extract_data", extract_data)
    monkeypatch.setattr(streamlit_app, "transform", transform_data)
    monkeypatch.setattr(streamlit_app, "format_summary", lambda stats: ["received: 1"])
    monkeypatch.setattr(streamlit_app, "load_tables", load_data)
    monkeypatch.setattr(streamlit_app.psycopg2, "connect", MagicMock(return_value=connection))
    for name in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        monkeypatch.setenv(name, "test")

    with pytest.raises(RuntimeError, match="API unavailable"):
        streamlit_app.run_pipeline()
    load_data.assert_not_called()

    assert streamlit_app.run_pipeline() == ["received: 1"]
    transform_data.assert_called_once_with([{"id": "1"}])
    load_data.assert_called_once_with(connection, {"respondents": []})
    connection.close.assert_called_once()


def test_dashboard_does_not_run_pipeline(monkeypatch):
    extract_data = MagicMock(side_effect=AssertionError("dashboard must not run ETL"))
    monkeypatch.setattr("extract.extract_data", extract_data)
    app = AppTest.from_file(Path(__file__).resolve().parent.parent / "streamlit_app.py").run()
    assert not app.exception
    assert app.title[0].value == "NCVS Victimization Dashboard"
    extract_data.assert_not_called()
