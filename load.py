"""Extract, transform, and upsert NCVS data into PostgreSQL."""
import pandas as pd
import psycopg
from psycopg import sql

from extract import extract_data
from transform import format_summary, transform


SCHEMA = """
CREATE TABLE IF NOT EXISTS respondents (
    idper TEXT NOT NULL, yearq TEXT NOT NULL, year SMALLINT, ager SMALLINT,
    sex SMALLINT, hispanic SMALLINT, race SMALLINT, race_ethnicity SMALLINT,
    hincome1 SMALLINT, hincome2 SMALLINT, marital SMALLINT, popsize SMALLINT,
    region SMALLINT, msa SMALLINT, locality SMALLINT, educatn1 SMALLINT,
    educatn2 SMALLINT, veteran SMALLINT, citizen SMALLINT,
    PRIMARY KEY (idper, yearq)
);
CREATE TABLE IF NOT EXISTS offense_types (
    newoff SMALLINT PRIMARY KEY, newcrime SMALLINT, seriousviolent SMALLINT,
    offense_name TEXT
);
CREATE TABLE IF NOT EXISTS victimizations (
    victimization_id TEXT PRIMARY KEY, idper TEXT, yearq TEXT, newoff SMALLINT,
    notify SMALLINT, vicservices SMALLINT, locationr SMALLINT, direl SMALLINT,
    weapon SMALLINT, weapcat SMALLINT, injury SMALLINT, serious SMALLINT,
    treatment SMALLINT, offenderage SMALLINT, offendersex SMALLINT,
    offtracenew SMALLINT, wgtviccy DOUBLE PRECISION, series SMALLINT,
    newwgt DOUBLE PRECISION, updated_at TIMESTAMPTZ,
    FOREIGN KEY (idper, yearq) REFERENCES respondents (idper, yearq),
    FOREIGN KEY (newoff) REFERENCES offense_types (newoff)
);
"""

KEYS = {
    "offense_types": ("newoff",),
    "respondents": ("idper", "yearq"),
    "victimizations": ("victimization_id",),
}


def sql_value(value):
    """Convert pandas missing values and scalars to PostgreSQL-friendly values."""
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value.item() if hasattr(value, "item") else value


def load_tables(connection, tables):
    """Create tables and upsert all transformed rows as one transaction."""
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA)
            for name, keys in KEYS.items():
                frame = tables[name]
                columns = list(frame.columns)
                updates = [c for c in columns if c not in keys]
                query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) "
                                "ON CONFLICT ({}) DO UPDATE SET {}").format(
                    sql.Identifier(name),
                    sql.SQL(", ").join(map(sql.Identifier, columns)),
                    sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                    sql.SQL(", ").join(map(sql.Identifier, keys)),
                    sql.SQL(", ").join(
                        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
                        for c in updates
                    ),
                )
                rows = (tuple(sql_value(value) for value in row)
                        for row in frame.itertuples(index=False, name=None))
                cursor.executemany(query, rows)


def main():
    tables, stats = transform(extract_data())
    for line in format_summary(stats):
        print(line)
    # libpq reads PGHOST, PGPORT, PGDATABASE, PGUSER and PGPASSWORD.
    with psycopg.connect() as connection:
        load_tables(connection, tables)
    for name in KEYS:
        print(f"{name}: {len(tables[name]):,} rows loaded")


if __name__ == "__main__":
    main()
