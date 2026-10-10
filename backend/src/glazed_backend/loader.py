"""Load the clean Parquet files into Postgres schema `glazed` as tables `ds_<name>` (idempotent: replace)."""
from __future__ import annotations

import glob
import os
import sys

import duckdb
import psycopg

_TYPES = {"VARCHAR": "text", "DATE": "date", "INTEGER": "integer", "BIGINT": "bigint", "DOUBLE": "double precision",
          "BOOLEAN": "boolean", "HUGEINT": "numeric", "TIMESTAMP": "timestamp", "FLOAT": "real",
          "SMALLINT": "smallint", "TINYINT": "smallint"}


def load_parquet_dir(directory: str, url: str, schema: str = "glazed", prefix: str = "ds_",
                     chunk: int = 50_000) -> dict[str, int]:
    out: dict[str, int] = {}
    src = duckdb.connect()
    with psycopg.connect(url) as pg:
        pg.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        for path in sorted(glob.glob(os.path.join(directory, "*.parquet"))):
            name = os.path.splitext(os.path.basename(path))[0]
            table = f"{schema}.{prefix}{name}"
            cur = src.execute("SELECT * FROM read_parquet(?)", [path])
            cols = [(d[0], _TYPES.get(str(d[1]).split("(")[0], "text")) for d in cur.description]
            ddl = ", ".join(f'"{c}" {t}' for c, t in cols)
            with pg.transaction():
                pg.execute(f"DROP TABLE IF EXISTS {table}")
                pg.execute(f"CREATE TABLE {table} ({ddl})")
                n = 0
                with pg.cursor().copy(f"COPY {table} FROM STDIN") as cp:
                    while rows := cur.fetchmany(chunk):
                        for r in rows:
                            cp.write_row(r)
                        n += len(rows)
            out[name] = n
    return out


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GLAZED_PARQUET_DIR", "../data/clean")
    url = os.environ.get("GLAZED_DATABASE_URL", "postgresql://glazed_app:glazed_dev@localhost:55432/glazed_app")
    for t, n in load_parquet_dir(d, url).items():
        print(f"{t}: {n}")
