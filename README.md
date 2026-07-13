
# micropython-tsdb

A tiny time-series database / datalake for [MicroPython](https://micropython.org/).

## Status
**PROTOTYPE**. WORK IN PROGRESS.
Not suitable for general consumption yet.

## Features

- Fast lookup of data
- Low memory usage, using streaming
- Partitioned on-disk layout. Apache Hive style
- Supports 16-bit integer array
- Per-resource configurable chunk storage (columnar/row-based/compressed)
- No external dependencies outside of MicroPython standard library
- Optional HTTP API integation for MicroDot
- Optional timeseries-aware compression (delta-encoding + simple9 packing)

