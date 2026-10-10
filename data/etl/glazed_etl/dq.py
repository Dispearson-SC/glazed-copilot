"""Data-quality log: one row per (table, rule) with the treatment and affected row count."""
from __future__ import annotations

TREATMENTS = ("fixed", "flagged", "excluded")


class DQLog:
    def __init__(self) -> None:
        self.entries: list[tuple] = []

    def add(self, table: str, rule_id: str, issue: str, treatment: str, affected_rows: int, notes: str = "") -> None:
        if treatment not in TREATMENTS:
            raise ValueError(f"treatment must be one of {TREATMENTS}, got {treatment!r}")
        self.entries.append((table, rule_id, issue, treatment, int(affected_rows), notes))

    def add_sql(self, con, table: str, rule_id: str, issue: str, treatment: str, count_sql: str, notes: str = "") -> int:
        """Log the single integer returned by ``count_sql`` (zero is logged too: the rule was checked)."""
        n = con.execute(count_sql).fetchone()[0] or 0
        self.add(table, rule_id, issue, treatment, n, notes)
        return n

    def write(self, con, name: str = "dq_log") -> None:
        con.execute(
            f"create or replace table {name}(table_name VARCHAR, rule_id VARCHAR, issue VARCHAR, "
            "treatment VARCHAR, affected_rows BIGINT, notes VARCHAR)"
        )
        if self.entries:
            con.executemany(f"insert into {name} values (?,?,?,?,?,?)", self.entries)
