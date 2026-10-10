"""Seed baseline promo-evaluation experiences into each store's Backboard memory.

Usage: PYTHONPATH=.deps:src python3 scripts/seed_experiences.py --stores S030,S001 [--md path]
Needs BACKBOARD_API_KEY (and GLAZED_STORAGE/GLAZED_DATABASE_URL to persist assistant ids in Postgres).
"""
import argparse
import os
import sys

from glazed_backend.adapters.driven.backboard_memory import BackboardMemory
from glazed_backend.adapters.driven.memory import InMemoryAssistants
from glazed_backend.application.seed import parse_promo_baseline

DEFAULT_MD = os.path.join(os.path.dirname(__file__), "../../../Dataset/analisis_estado.md")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", default="S030")
    ap.add_argument("--md", default=DEFAULT_MD)
    a = ap.parse_args()
    key = os.environ.get("BACKBOARD_API_KEY", "")
    if not key:
        print("BACKBOARD_API_KEY is not set", file=sys.stderr)
        return 1
    assistants = InMemoryAssistants()
    if os.environ.get("GLAZED_STORAGE") == "postgres":
        from glazed_backend.adapters.driven.postgres import PostgresStore
        store = PostgresStore(os.environ["GLAZED_DATABASE_URL"])
        store.migrate()
        assistants = store.assistants
    mem = BackboardMemory(key, assistants)
    text = open(a.md, encoding="utf-8").read()
    for sid in a.stores.split(","):
        exps = parse_promo_baseline(text, sid)
        for e in exps:
            mem.remember(sid, e)
        print(f"{sid}: seeded {len(exps)} experiences")
    return 0


if __name__ == "__main__":
    sys.exit(main())
