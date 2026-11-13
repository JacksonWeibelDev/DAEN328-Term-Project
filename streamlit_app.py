"""Streamlit entry point and NCVS data pipeline."""
import os
import sys
from contextlib import closing
from datetime import datetime, timezone

import psycopg2
import streamlit as st
from dotenv import load_dotenv

from extract import extract_data
from load import get_checkpoint, load_tables
from transform import format_summary, transform


def run_pipeline():
    """Extract, transform, and load records changed since the last success."""
    started = datetime.now(timezone.utc)
    load_dotenv()
    with closing(psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )) as connection:
        checkpoint = get_checkpoint(connection)
        since = checkpoint.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") if checkpoint else None
        records = extract_data(updated_since=since)
        tables, stats = transform(records)
        if checkpoint and not records:
            tables["offense_types"] = tables["offense_types"].iloc[:0]
        timestamps = (datetime.fromisoformat(r[":updated_at"].replace("Z", "+00:00"))
                      for r in records)
        latest = max((t.replace(tzinfo=timezone.utc) if t.tzinfo is None
                      else t.astimezone(timezone.utc) for t in timestamps), default=None)
        counts = load_tables(connection, tables, latest)
    lines = [f"ETL run {started:%Y-%m-%d %H:%M:%S} UTC",
             f"extraction: {'incremental since ' + since + ' UTC' if since else 'initial full pull'}"]
    lines.extend(format_summary(stats))
    lines.extend(f"{name}: {count['inserted']:,} inserted, {count['updated']:,} updated"
                 for name, count in counts.items())
    return lines


def main():
    st.title("NCVS Victimization Dashboard")
    st.write("Data loaded successfully. The dashboard is under construction.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--etl"]:
        for line in run_pipeline():
            print(line, flush=True)
    else:
        main()
