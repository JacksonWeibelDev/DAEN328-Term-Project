"""PostgreSQL integration test; set TEST_POSTGRES=1 to run it."""
import os
import uuid
from contextlib import closing

import psycopg2
import pytest
from psycopg2 import sql

from load import load_tables
from test_transform import _raw_record
from transform import transform


@pytest.mark.skipif(os.environ.get("TEST_POSTGRES") != "1", reason="PostgreSQL not configured")
def test_load_upserts_and_rolls_back():
    schema = "test_load_" + uuid.uuid4().hex
    with closing(psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )) as conn:
        cursor = conn.cursor()
        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        conn.commit()
        try:
            tables, _ = transform([_raw_record(1)])
            load_tables(conn, tables)
            tables["victimizations"].loc[0, "notify"] = 1
            load_tables(conn, tables)
            cursor.execute("SELECT count(*) FROM respondents")
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT count(*) FROM offense_types")
            assert cursor.fetchone()[0] == 5
            cursor.execute("SELECT notify, weapcat FROM victimizations")
            assert cursor.fetchone() == (1, 0)
            cursor.execute("SELECT hincome1 FROM respondents")
            assert cursor.fetchone()[0] is None
            conn.commit()

            tables["respondents"].loc[0, "sex"] = 2
            tables["victimizations"].loc[0, "newoff"] = 99
            with pytest.raises(psycopg2.errors.ForeignKeyViolation):
                load_tables(conn, tables)
            cursor.execute("SELECT sex FROM respondents")
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT newoff FROM victimizations")
            assert cursor.fetchone()[0] == 4
        finally:
            conn.rollback()
            cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
            conn.commit()
            cursor.close()
