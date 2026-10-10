# Vendored dependencies

## dataset-road2tech (git submodule)

The raw challenge dataset (SOFTEK Road To Tech 2026, "Tienda Inteligente para Retail") is not copied into this
repository. It is pinned as a git submodule pointing at the organizers' original repository:

- Source: https://github.com/ams-innovation/dataset-hacktahton-road2tech (branch `master`)
- Path: `vendor/dataset-road2tech/`

Fetch it after cloning:

```sh
git submodule update --init --recursive
```

The cleaned tables, the DuckDB file and the forecast parquet are derived artifacts produced by the ETL and
forecast scripts from these raw CSVs; they are not versioned here. Point the backend at the raw layer with
`GLAZED_RAW_PATH` when running the integrity detectors.
