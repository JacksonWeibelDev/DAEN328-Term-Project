"""Streamlit entry point and NCVS data pipeline."""
import os
import sys
from contextlib import closing

import psycopg2
import streamlit as st
from dotenv import load_dotenv

from extract import extract_data
from load import load_tables
from transform import format_summary, transform


def run_pipeline():
    """Extract, transform, and load all NCVS records."""
    tables, stats = transform(extract_data())
    load_dotenv()
    with closing(psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )) as connection:
        load_tables(connection, tables)
    return format_summary(stats)


def main():
    st.title("NCVS Victimization Dashboard")
    st.write("Data loaded successfully. The dashboard is under construction.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--etl"]:
        for line in run_pipeline():
            print(line, flush=True)
    else:
        main()
