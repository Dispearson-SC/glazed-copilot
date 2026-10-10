# Data pipeline

Turns the organizers' raw CSVs (`../vendor/dataset-road2tech`, a git submodule) into the derived data the service reads.
Nothing here is versioned except code: `clean/` and `forecast/out/` are git-ignored and rebuilt by `make data`.

```
vendor/dataset-road2tech/*.csv --glazed_etl--> data/clean/*.parquet + glazed.duckdb (+ dq_log.csv, validation.json)
data/clean/*.parquet --forecast run--> data/forecast/out/forecast.parquet (+ metrics_*.csv, run_meta.json)
```

| Path | Content |
|---|---|
| `etl/glazed_etl/` | cleaning ETL (DuckDB). Builds the typed Parquet tables and `glazed.duckdb` (tables plus views `v_sales_enriched`, `v_demand_sales`, `v_store_day`, `v_inventory_waste`, `v_store_day_weather`). |
| `forecast/forecast/` | holdout forecast job. Trains on the first 80% of the span and scores the rest with three models (`glm_poisson`, `ma28_weekday`, `seasonal_naive`); the backend reads only `glm_poisson` (`GLAZED_FORECAST_MODEL`). |
| `docs/` | `data_quality.md` (what the ETL fixes or flags) and `analisis_estado.md` (baseline analysis seeded into the experience memory). |
| `build.sh` | runs both stages; used by the `data-build` container and by `make data-local`. |

## Build

```sh
make data          # from the repository root: one-shot python:3.12 container, outputs land in data/
make data-local    # same without Docker: pip install -r data/requirements.txt first
```

Expect a few minutes (ETL about 12 s, forecast about 3.5 min) and about 3 GB of RAM.
The ETL exits non-zero if a validation check fails; the forecast exits non-zero if its no-leakage check fails.

## Tests

```sh
pip install -r data/requirements-dev.txt
cd data/etl      && python -m pytest -q
cd data/forecast && python -m pytest -q
```

The ETL tests use small CSV fixtures (`etl/tests/fixtures/raw_min`, `etl/tests/helpers.py`); they do not need the dataset.
