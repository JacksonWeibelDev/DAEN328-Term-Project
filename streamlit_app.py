"""Streamlit entry point and NCVS data pipeline."""
import os
import sys
from contextlib import closing
from datetime import datetime, timezone

import psycopg2
import pandas as pd
import altair as alt
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



# Official NCVS Select codebook:
# https://bjs.ojp.gov/document/NCVS_Select_person_level_codebook.pdf
RELATIONSHIP_LABELS = {
    1: "Intimates",
    2: "Other relatives",
    3: "Acquaintances",
    4: "Strangers",
}
WEAPON_LABELS = {1: "Weapon present", 2: "No weapon"}
INJURY_LABELS = {0: "Not injured", 1: "Injured"}
AGE_LABELS = {
    1: "12–17", 2: "18–24", 3: "25–34",
    4: "35–49", 5: "50–64", 6: "65+",
}
REGION_LABELS = {1: "Northeast", 2: "Midwest", 3: "South", 4: "West"}
SEX_LABELS = {1: "Male", 2: "Female"}

# Codes come from the NCVS tables; "All" never removes unknown or missing codes.
FILTER_LABELS = {
    "ager": AGE_LABELS,
    "region": REGION_LABELS,
    "sex": SEX_LABELS,
    "direl": RELATIONSHIP_LABELS,
    "weapon": WEAPON_LABELS,
    "injury": INJURY_LABELS,
}
FILTER_WIDGET_KEYS = (
    "filter_years", "filter_offenses", "filter_age", "filter_region",
    "filter_sex", "filter_relationship", "filter_weapon", "filter_injury",
)


def reset_dashboard_filters():
    """Clear sidebar widget selections so their defaults are restored."""
    for key in FILTER_WIDGET_KEYS:
        st.session_state.pop(key, None)


def apply_dashboard_filters(frame, year_start, year_end, offenses, categories):
    """Apply all sidebar filters without excluding missing codes by default.

    categories maps database column names to a label or "All".
    """
    mask = (
        frame["year"].between(year_start, year_end)
        & frame["offense_name"].isin(offenses)
    )
    for column, selected_label in categories.items():
        if selected_label == "All":
            continue
        codes = [code for code, label in FILTER_LABELS[column].items()
                 if label == selected_label]
        mask &= frame[column].isin(codes)
    return frame.loc[mask].copy()


@st.cache_data(ttl=600, show_spinner="Loading NCVS records from PostgreSQL...")
def get_dashboard_data():
    """Read data from the ETL-created tables (without rerunning the ETL)."""
    load_dotenv()
    with closing(psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    v.victimization_id,
                    r.year,
                    r.ager,
                    r.region,
                    r.sex,
                    o.offense_name,
                    v.notify,
                    v.direl,
                    v.weapon,
                    v.injury,
                    v.wgtviccy
                FROM victimizations AS v
                JOIN respondents AS r
                  ON v.idper = r.idper AND v.yearq = r.yearq
                JOIN offense_types AS o
                  ON v.newoff = o.newoff
            """)
            names = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=names)


def reporting_summary(frame, group_columns):
    """Weighted reporting percentage for one or more category columns.

    Denominator: annual victimization weights for notify = 1 or 2.
    Numerator: annual victimization weights for notify = 1.
    sample_n is the unweighted number of eligible source records.
    """
    if isinstance(group_columns, str):
        group_columns = [group_columns]
    columns = group_columns + ["sample_n", "weight_total", "weight_reported", "reported_pct"]
    valid = frame.loc[
        frame["notify"].isin([1, 2])
        & frame["wgtviccy"].notna()
        & (frame["wgtviccy"] > 0)
    ].copy()
    if valid.empty:
        return pd.DataFrame(columns=columns)

    valid["reported_weight"] = valid["wgtviccy"].where(valid["notify"] == 1, 0.0)
    groups = (
        valid.groupby(group_columns, dropna=True)
        .agg(
            sample_n=("victimization_id", "size"),
            weight_total=("wgtviccy", "sum"),
            weight_reported=("reported_weight", "sum"),
        )
        .reset_index()
    )
    groups["reported_pct"] = 100 * groups["weight_reported"] / groups["weight_total"]
    return groups[columns]


def horizontal_reporting_chart(summary, category_col, order=None, height=270):
    """Reusable horizontal bar chart with consistent axes and informative tooltips."""
    if order is None:
        y = alt.Y(f"{category_col}:N", sort="-x", title=None)
    else:
        y = alt.Y(f"{category_col}:N", sort=order, title=None)
    return (
        alt.Chart(summary)
        .mark_bar(cornerRadiusEnd=4, color="#167c99")
        .encode(
            x=alt.X("reported_pct:Q", title="Reported to police (%)",
                    scale=alt.Scale(domain=[0, 100])),
            y=y,
            tooltip=[
                alt.Tooltip(f"{category_col}:N", title="Category"),
                alt.Tooltip("reported_pct:Q", title="Reported (%)", format=".1f"),
                alt.Tooltip("sample_n:Q", title="Sample records", format=",d"),
            ],
        )
        .properties(height=height)
    )


def labeled_summary(frame, column, labels):
    """Remove missing/unknown categories and turn documented codes into labels."""
    eligible = frame.loc[frame[column].isin(labels)].copy()
    if eligible.empty:
        return pd.DataFrame(columns=["category", "sample_n", "reported_pct"])
    eligible["category"] = eligible[column].map(labels)
    return reporting_summary(eligible, "category")


def main():
    st.set_page_config(page_title="NCVS | Police Reporting", layout="wide")
    st.title("NCVS | Police Reporting Dashboard")
    st.write(
        "**Why are some victimizations reported to the police while others are not?** "
        "Explore five questions about crime types, trends, relationships, "
        "weapons and injuries, and demographics. Scroll down to see all five analyses."
    )

    try:
        df = get_dashboard_data()
    except (psycopg2.Error, KeyError) as exc:
        st.error(
            "Cannot read the NCVS PostgreSQL database. Start Docker Desktop "
            "and make sure `docker compose up --build -d` has completed successfully."
        )
        st.code(str(exc))
        return

    if df.empty:
        st.warning("No victimization records are loaded in the database yet.")
        return

    for col in ("year", "ager", "region", "sex", "notify", "direl", "weapon", "injury", "wgtviccy"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["year", "offense_name"]).copy()
    if df.empty:
        st.warning("No rows have both a survey year and a valid offense name.")
        return
    df["year"] = df["year"].astype(int)

    # Every sidebar selection updates all five charts.
    st.sidebar.header("Dashboard filters")
    st.sidebar.button("Reset all filters", on_click=reset_dashboard_filters,
                      use_container_width=True)
    st.sidebar.subheader("Time and victimization")
    start, end = int(df["year"].min()), int(df["year"].max())
    if start == end:
        year_start, year_end = start, end
        st.sidebar.write(f"Survey year: {start}")
    else:
        year_start, year_end = st.sidebar.slider(
            "Survey year range", start, end, (start, end), key="filter_years"
        )
    offenses = sorted(df["offense_name"].dropna().unique().tolist())
    selected_offenses = st.sidebar.multiselect(
        "Victimization type", offenses, default=offenses, key="filter_offenses"
    )

    st.sidebar.subheader("Victim demographics")
    age_choice = st.sidebar.selectbox(
        "Age group", ["All", *AGE_LABELS.values()], key="filter_age"
    )
    region_choice = st.sidebar.selectbox(
        "Region", ["All", *REGION_LABELS.values()], key="filter_region"
    )
    sex_choice = st.sidebar.selectbox(
        "Sex", ["All", *SEX_LABELS.values()], key="filter_sex"
    )

    st.sidebar.subheader("Victimization circumstances")
    relationship_choice = st.sidebar.selectbox(
        "Victim-offender relationship", ["All", *RELATIONSHIP_LABELS.values()],
        key="filter_relationship"
    )
    weapon_choice = st.sidebar.selectbox(
        "Weapon presence", ["All", *WEAPON_LABELS.values()], key="filter_weapon"
    )
    injury_choice = st.sidebar.selectbox(
        "Injury", ["All", *INJURY_LABELS.values()], key="filter_injury"
    )
    st.sidebar.caption("All five charts update together. 'All' keeps missing and unknown values.")
    if st.sidebar.button("Refresh data from database", use_container_width=True):
        get_dashboard_data.clear()
        st.rerun()

    filtered = apply_dashboard_filters(
        df, year_start, year_end, selected_offenses,
        {
            "ager": age_choice,
            "region": region_choice,
            "sex": sex_choice,
            "direl": relationship_choice,
            "weapon": weapon_choice,
            "injury": injury_choice,
        },
    )
    valid = filtered.loc[
        filtered["notify"].isin([1, 2]) & (filtered["wgtviccy"] > 0)
    ].copy()

    if valid.empty:
        st.info("The current filters have no records with known police reporting and a positive weight.")
        return

    total_weight = valid["wgtviccy"].sum()
    reported_weight = valid.loc[valid["notify"] == 1, "wgtviccy"].sum()
    pct = 100 * reported_weight / total_weight
    overview1, overview2, overview3, overview4 = st.columns(4)
    overview1.metric("Reported to police", f"{pct:.1f}%")
    overview2.metric("Not reported", f"{100 - pct:.1f}%")
    overview3.metric("Sample victimizations", f"{len(valid):,}")
    overview4.metric("Years in selection", f"{valid['year'].nunique():,}")
    st.caption(
        "Weighted percentages use `wgtviccy`, the annual victimization weight. "
        "Only `notify = 1` (reported) and `notify = 2` (not reported) and positive "
        "weights are included; sample counts are unweighted."
    )

    # ------------------------------------------------------------------
    # Question 1: Victimization type
    # ------------------------------------------------------------------
    st.divider()
    st.header("1. Which types of victimizations are most and least likely to be reported?")
    st.write("Compare the share of each crime type that was reported to police.")
    crime = reporting_summary(valid, "offense_name")
    if not crime.empty:
        crime = crime.sort_values("reported_pct", ascending=False)
        st.altair_chart(
            horizontal_reporting_chart(crime, "offense_name", height=250),
            use_container_width=True,
        )
        with st.expander("View crime-type reporting table"):
            st.dataframe(
                crime[["offense_name", "reported_pct", "sample_n"]].rename(
                    columns={"offense_name": "Victimization type",
                             "reported_pct": "Reported (%)", "sample_n": "Sample records"}
                ).round({"Reported (%)": 1}),
                hide_index=True, use_container_width=True,
            )

    # ------------------------------------------------------------------
    # Question 2: Change over time
    # ------------------------------------------------------------------
    st.divider()
    st.header("2. How have police reporting patterns changed over time?")
    st.write("Track the weighted percentage reported to police by survey year.")
    compare = st.checkbox("Compare individual victimization types", value=False)
    if compare:
        yearly = reporting_summary(valid, ["year", "offense_name"])
        line_chart = (
            alt.Chart(yearly)
            .mark_line(point=True)
            .encode(
                x=alt.X("year:Q", title="Survey year", axis=alt.Axis(format="d")),
                y=alt.Y("reported_pct:Q", title="Reported to police (%)",
                        scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("offense_name:N", title="Victimization type"),
                tooltip=["year:Q", "offense_name:N",
                         alt.Tooltip("reported_pct:Q", format=".1f", title="Reported (%)"),
                         alt.Tooltip("sample_n:Q", format=",d", title="Sample records")],
            )
            .properties(height=360)
        )
    else:
        yearly = reporting_summary(valid, "year").sort_values("year")
        line_chart = (
            alt.Chart(yearly)
            .mark_line(point=True, color="#167c99")
            .encode(
                x=alt.X("year:Q", title="Survey year", axis=alt.Axis(format="d")),
                y=alt.Y("reported_pct:Q", title="Reported to police (%)",
                        scale=alt.Scale(domain=[0, 100])),
                tooltip=["year:Q",
                         alt.Tooltip("reported_pct:Q", format=".1f", title="Reported (%)"),
                         alt.Tooltip("sample_n:Q", format=",d", title="Sample records")],
            )
            .properties(height=360)
        )
    if not yearly.empty:
        st.altair_chart(line_chart, use_container_width=True)
    else:
        st.info("No yearly observations are available with the current filters.")

    # ------------------------------------------------------------------
    # Question 3: Victim-offender relationship
    # ------------------------------------------------------------------
    st.divider()
    st.header("3. How does the victim-offender relationship relate to police reporting?")
    st.write("Compare reported percentages for known victim-offender relationships.")
    relationships = labeled_summary(valid, "direl", RELATIONSHIP_LABELS)
    if relationships.empty:
        st.info("No incidents with a known relationship category match your current filters.")
    else:
        st.altair_chart(
            horizontal_reporting_chart(
                relationships, "category",
                order=list(RELATIONSHIP_LABELS.values()), height=230
            ),
            use_container_width=True,
        )
        with st.expander("View relationship comparison table"):
            st.dataframe(
                relationships[["category", "reported_pct", "sample_n"]]
                .rename(columns={"category": "Victim-offender relationship",
                                 "reported_pct": "Reported (%)", "sample_n": "Sample records"})
                .round({"Reported (%)": 1}),
                hide_index=True, use_container_width=True,
            )

    # ------------------------------------------------------------------
    # Question 4: Weapon presence and injury
    # ------------------------------------------------------------------
    st.divider()
    st.header("4. Are victimizations involving weapons or injuries more frequently reported?")
    st.write("Compare the reporting rate when a weapon was present, and when the victim was injured.")
    weapon_result = labeled_summary(valid, "weapon", WEAPON_LABELS)
    injury_result = labeled_summary(valid, "injury", INJURY_LABELS)
    weapon_col, injury_col = st.columns(2)
    with weapon_col:
        st.subheader("Weapon presence")
        if weapon_result.empty:
            st.info("No valid weapon-present/absent answers match these filters.")
        else:
            st.altair_chart(
                horizontal_reporting_chart(weapon_result, "category",
                                           order=list(WEAPON_LABELS.values()), height=190),
                use_container_width=True,
            )
    with injury_col:
        st.subheader("Injury")
        if injury_result.empty:
            st.info("No valid injured/not-injured answers match these filters.")
        else:
            st.altair_chart(
                horizontal_reporting_chart(injury_result, "category",
                                           order=list(INJURY_LABELS.values()), height=190),
                use_container_width=True,
            )

    # ------------------------------------------------------------------
    # Question 5: Age and region
    # ------------------------------------------------------------------
    st.divider()
    st.header("5. How do reporting patterns differ by age group and region?")
    st.write(
        "Each square is the weighted percentage of victimizations reported to "
        "police for an age group within a census region. Darker blue indicates a higher percentage."
    )
    regional = valid.loc[
        valid["ager"].isin(AGE_LABELS) & valid["region"].isin(REGION_LABELS)
    ].copy()
    if regional.empty:
        st.info("No records with valid age and region codes match your filters.")
    else:
        regional["age_group"] = regional["ager"].map(AGE_LABELS)
        regional["region_name"] = regional["region"].map(REGION_LABELS)
        matrix = reporting_summary(regional, ["age_group", "region_name"])
        matrix["rate_label"] = matrix["reported_pct"].map(lambda rate: f"{rate:.1f}%")
        heatmap_base = alt.Chart(matrix).encode(
            x=alt.X("region_name:N", title="U.S. census region",
                    sort=list(REGION_LABELS.values())),
            y=alt.Y("age_group:N", title="Victim age",
                    sort=list(AGE_LABELS.values())),
            tooltip=[
                alt.Tooltip("age_group:N", title="Age group"),
                alt.Tooltip("region_name:N", title="Region"),
                alt.Tooltip("reported_pct:Q", format=".1f", title="Reported (%)"),
                alt.Tooltip("sample_n:Q", format=",d", title="Sample records"),
            ],
        )
        cells = heatmap_base.mark_rect().encode(
            color=alt.Color("reported_pct:Q", title="Reported (%)",
                            scale=alt.Scale(domain=[0, 100], scheme="blues")),
        )
        labels = heatmap_base.mark_text(fontSize=12, fontWeight="bold").encode(
            text="rate_label:N",
            color=alt.condition("datum.reported_pct >= 65", alt.value("white"),
                                alt.value("#17365d")),
        )
        st.altair_chart((cells + labels).properties(height=315), use_container_width=True)
        with st.expander("View the age-by-region data"):
            st.dataframe(
                matrix[["age_group", "region_name", "reported_pct", "sample_n"]]
                .rename(columns={"age_group": "Age group", "region_name": "Region",
                                 "reported_pct": "Reported (%)", "sample_n": "Sample records"})
                .round({"Reported (%)": 1}),
                hide_index=True, use_container_width=True,
            )

    st.divider()
    with st.expander("Methodology, data definitions, and data preview"):
        st.markdown(
            "**Calculation:** The rate shown for a group is "
            "`100 × sum(wgtviccy where notify=1) / sum(wgtviccy where notify in [1,2])`. "
            "All positive-weight observations are included; `notify=3` (don't know) "
            "and missing/invalid answers are excluded. "
            "Changing sidebar filters updates all five sections. "
            "The percentages are survey-weighted descriptive estimates and "
            "do not include confidence intervals or survey-design variance estimation."
        )
        st.markdown(
            "**Reference:** [BJS NCVS Select codebook]"
            "(https://bjs.ojp.gov/document/NCVS_Select_person_level_codebook.pdf)"
        )
        st.dataframe(valid.head(25), hide_index=True, use_container_width=True)
    st.caption("Source: Bureau of Justice Statistics, NCVS Select – Personal Victimization dataset.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--etl"]:
        for line in run_pipeline():
            print(line, flush=True)
    else:
        main()
