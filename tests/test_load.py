"""PostgreSQL integration test; set TEST_POSTGRES=1 to run it."""
import os
import uuid

import psycopg
import pytest
from psycopg import sql

from load import load_tables
from test_transform import _raw_record
from transform import transform


@pytest.mark.skipif(os.environ.get("TEST_POSTGRES") != "1", reason="PostgreSQL not configured")
def test_load_upserts_and_rolls_back():
    schema = "test_load_" + uuid.uuid4().hex
    with psycopg.connect(autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            tables, _ = transform([_raw_record(1)])
            load_tables(conn, tables)
            tables["victimizations"].loc[0, "notify"] = 1
            load_tables(conn, tables)
            assert conn.execute("SELECT count(*) FROM respondents").fetchone()[0] == 1
            assert conn.execute("SELECT count(*) FROM offense_types").fetchone()[0] == 5
            assert conn.execute("SELECT notify, weapcat FROM victimizations").fetchone() == (1, 0)
            assert conn.execute("SELECT hincome1 FROM respondents").fetchone()[0] is None

            tables["respondents"].loc[0, "sex"] = 2
            tables["victimizations"].loc[0, "newoff"] = 99
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                load_tables(conn, tables)
            assert conn.execute("SELECT sex FROM respondents").fetchone()[0] == 1
            assert conn.execute("SELECT newoff FROM victimizations").fetchone()[0] == 4
        finally:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
