#!/bin/sh
# Raw CSVs -> clean Parquet + glazed.duckdb -> holdout forecast.
#   RAW  directory with the 13 raw CSVs (default: the vendor/dataset-road2tech submodule)
# Outputs (git-ignored): data/clean/ and data/forecast/out/forecast.parquet
# Needs the packages in data/requirements.txt (the `data-build` docker service has them).
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
RAW=${RAW:-$HERE/../vendor/dataset-road2tech}
PY=${PY:-python3}

if [ ! -f "$RAW/sales_daily.csv" ]; then
  echo "raw CSVs not found in $RAW (run: git submodule update --init --recursive)" >&2
  exit 2
fi

echo "== 1/2 ETL: $RAW -> $HERE/clean"
(cd "$HERE/etl" && PYTHONPATH=. "$PY" -m glazed_etl --raw "$RAW" --out "$HERE/clean")

echo "== 2/2 forecast: $HERE/clean -> $HERE/forecast/out"
(cd "$HERE/forecast" && PYTHONPATH=. "$PY" -m forecast run --clean "$HERE/clean" --out "$HERE/forecast/out")
# The backend reads forecast.parquet (GLAZED_FORECAST_PATH); the job writes forecast_holdout.parquet.
mv "$HERE/forecast/out/forecast_holdout.parquet" "$HERE/forecast/out/forecast.parquet"
echo "done: $HERE/clean/glazed.duckdb and $HERE/forecast/out/forecast.parquet"
