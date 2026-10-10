"""User administration. Passwords come from stdin only, never from an argument.

    python -m glazed_backend.scripts.users add --email a@b.c --name "A" --role manager --stores S001,S002 --password-stdin
    python -m glazed_backend.scripts.users list
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from typing import Any

from ..application.auth import ManageUsers, PasswordHasher
from ..domain import DomainError


def _repo(env: dict[str, str]) -> Any:
    if env.get("GLAZED_STORAGE", "memory") != "postgres":
        raise SystemExit("users are persistent only with GLAZED_STORAGE=postgres (and GLAZED_DATABASE_URL)")
    from ..adapters.driven.postgres import PostgresStore
    store = PostgresStore(env["GLAZED_DATABASE_URL"])
    store.migrate()
    return store.users


def main(argv: list[str] | None = None, env: dict[str, str] | None = None, repo: Any = None, stdin: Any = None,
         out: Any = None) -> int:
    env = dict(os.environ if env is None else env)
    stdin, out = stdin or sys.stdin, out or sys.stdout
    ap = argparse.ArgumentParser(prog="glazed_backend.scripts.users")
    sub = ap.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="create the user, or update it if the email exists")
    add.add_argument("--email", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--role", required=True, choices=["admin", "manager"])
    add.add_argument("--stores", default="", help="comma-separated store ids (ignored by admin: all stores)")
    add.add_argument("--password-stdin", action="store_true", required=True, help="read the password from stdin")
    sub.add_parser("list", help="list users (never shows hashes)")
    a = ap.parse_args(argv)
    repo = repo if repo is not None else _repo(env)
    mgr = ManageUsers(repo, PasswordHasher())
    if a.cmd == "list":
        for u in mgr.list():
            print(f"{u.email}\t{u.role}\t{','.join(u.store_ids) or ('*' if u.role == 'admin' else '-')}\t"
                  f"{'active' if u.active else 'inactive'}\t{u.name}", file=out)
        return 0
    password = getpass.getpass("Password: ") if stdin.isatty() else stdin.readline().rstrip("\r\n")
    try:
        user, created = mgr.upsert(a.email, a.name, a.role, [s for s in a.stores.split(",") if s.strip()], password)
    except DomainError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"{'created' if created else 'updated'} {user.email} ({user.role})", file=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
