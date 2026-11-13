from unittest.mock import Mock

from extract import extract_data


def test_incremental_extraction_requests_only_later_timestamps(monkeypatch):
    response = Mock()
    response.json.return_value = [{":id": "1", ":updated_at": "2026-01-02T00:00:00Z"}]
    get = Mock(return_value=response)
    monkeypatch.setattr("extract.requests.get", get)

    records = extract_data(updated_since="2026-01-01T00:00:00.000000", page_size=10)

    assert len(records) == 1
    assert get.call_args.kwargs["params"]["$where"] == (
        ":updated_at > '2026-01-01T00:00:00.000000'"
    )
    assert get.call_args.kwargs["params"]["$order"] == ":updated_at ASC, :id ASC"
