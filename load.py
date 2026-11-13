"""Upsert transformed NCVS data into PostgreSQL."""
import pandas as pd
from psycopg2 import sql
from psycopg2.extras import execute_values
from itertools import islice


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
CREATE TABLE IF NOT EXISTS etl_checkpoint (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    updated_at TIMESTAMPTZ NOT NULL
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


def get_checkpoint(connection):
    """Return the last successfully loaded source timestamp, if one exists."""
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('etl_checkpoint')")
            if cursor.fetchone()[0] is None:
                return None
            cursor.execute("SELECT updated_at FROM etl_checkpoint WHERE singleton = TRUE")
            row = cursor.fetchone()
            return row[0] if row else None


def load_tables(connection, tables, checkpoint=None):
    """Atomically upsert the tables and checkpoint; return inserted/updated counts."""
    counts = {}
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA)
            for name, keys in KEYS.items():
                frame = tables[name]
                columns = list(frame.columns)
                updates = [c for c in columns if c not in keys]
                query = sql.SQL("INSERT INTO {} ({}) VALUES %s "
                                "ON CONFLICT ({}) DO UPDATE SET {} "
                                "RETURNING (xmax = 0)").format(
                    sql.Identifier(name),
                    sql.SQL(", ").join(map(sql.Identifier, columns)),
                    sql.SQL(", ").join(map(sql.Identifier, keys)),
                    sql.SQL(", ").join(
                        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
                        for c in updates
                    ),
                )
                rows = (tuple(sql_value(value) for value in row)
                        for row in frame.itertuples(index=False, name=None))
                inserted = updated = 0
                while batch := list(islice(rows, 1000)):
                    results = execute_values(cursor, query.as_string(connection), batch,
                                             page_size=1000, fetch=True)
                    inserted += sum(row[0] for row in results)
                    updated += len(results) - sum(row[0] for row in results)
                counts[name] = {"inserted": inserted, "updated": updated}
            if checkpoint is not None:
                cursor.execute(
                    "INSERT INTO etl_checkpoint (singleton, updated_at) VALUES (TRUE, %s) "
                    "ON CONFLICT (singleton) DO UPDATE SET updated_at = EXCLUDED.updated_at",
                    (checkpoint,),
                )
    return counts
