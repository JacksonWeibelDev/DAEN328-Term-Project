from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
import pandas as pd
from streamlit.testing.v1 import AppTest

import streamlit_app


def test_pipeline_calls_etl_functions_and_propagates_errors(monkeypatch):
    records = [{":updated_at": "2026-01-01T00:00:00Z"}]
    extract_data = MagicMock(side_effect=[RuntimeError("API unavailable"), records])
    transform_data = MagicMock(return_value=({"respondents": []}, {"received": 1}))
    load_data = MagicMock(return_value={"respondents": {"inserted": 1, "updated": 0}})
    connection = MagicMock()
    monkeypatch.setattr(streamlit_app, "extract_data", extract_data)
    monkeypatch.setattr(streamlit_app, "transform", transform_data)
    monkeypatch.setattr(streamlit_app, "format_summary", lambda stats: ["received: 1"])
    monkeypatch.setattr(streamlit_app, "load_tables", load_data)
    monkeypatch.setattr(streamlit_app, "get_checkpoint", MagicMock(return_value=None))
    monkeypatch.setattr(streamlit_app.psycopg2, "connect", MagicMock(return_value=connection))
    for name in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        monkeypatch.setenv(name, "test")

    with pytest.raises(RuntimeError, match="API unavailable"):
        streamlit_app.run_pipeline()
    load_data.assert_not_called()

    summary = streamlit_app.run_pipeline()
    assert "received: 1" in summary
    assert "respondents: 1 inserted, 0 updated" in summary
    transform_data.assert_called_once_with(records)
    load_data.assert_called_once_with(connection, {"respondents": []},
                                      datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert connection.close.call_count == 2


def test_dashboard_does_not_run_pipeline(monkeypatch):
    extract_data = MagicMock(side_effect=AssertionError("dashboard must not run ETL"))
    monkeypatch.setattr("extract.extract_data", extract_data)
    app = AppTest.from_file(Path(__file__).resolve().parent.parent / "streamlit_app.py").run()
    assert not app.exception
    assert app.title[0].value == "NCVS Victimization Dashboard"
    extract_data.assert_not_called()


def test_empty_incremental_run_preserves_checkpoint(monkeypatch):
    checkpoint = datetime(2026, 1, 1, tzinfo=timezone.utc)
    connection = MagicMock()
    extract_data = MagicMock(return_value=[])
    load_data = MagicMock(return_value={"offense_types": {"inserted": 0, "updated": 0}})
    monkeypatch.setattr(streamlit_app, "get_checkpoint", lambda conn: checkpoint)
    monkeypatch.setattr(streamlit_app, "extract_data", extract_data)
    monkeypatch.setattr(streamlit_app, "load_tables", load_data)
    monkeypatch.setattr(streamlit_app.psycopg2, "connect", MagicMock(return_value=connection))
    for name in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        monkeypatch.setenv(name, "test")

    summary = streamlit_app.run_pipeline()

    extract_data.assert_called_once_with(updated_since="2026-01-01T00:00:00.000000")
    assert load_data.call_args.args[2] is None
    assert isinstance(load_data.call_args.args[1]["offense_types"], pd.DataFrame)
    assert load_data.call_args.args[1]["offense_types"].empty
    assert "missing values: no records to clean" in summary
    assert "offense_types: 0 inserted, 0 updated" in summary
