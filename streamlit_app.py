"""Streamlit entry point and NCVS data pipeline."""
import psycopg
import streamlit as st

from extract import extract_data
from load import load_tables
from transform import format_summary, transform


@st.cache_resource(show_spinner=False)
def run_pipeline():
    """Run the full pipeline once per app process after a successful load."""
    tables, stats = transform(extract_data())
    with psycopg.connect() as connection:
        load_tables(connection, tables)
    return format_summary(stats)


def main():
    st.title("NCVS Victimization Dashboard")
    with st.spinner("Loading NCVS data..."):
        try:
            summary = run_pipeline()
        except Exception as error:
            st.error(f"Data load failed: {error}")
            st.info("Reload the page to retry.")
            return
    st.success("Data loaded successfully.")
    for line in summary:
        st.text(line)


if __name__ == "__main__":
    main()
