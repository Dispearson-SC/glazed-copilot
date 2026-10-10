"""glazed_metrics: pure, I/O-free reorder analytics used by the DuckDB adapter behind MetricsPort.

Functions take rows/series and return dataclasses or plain dicts. Nothing here reads a database or
the clock; the as_of guard lives in the adapter that builds the inputs.
"""
