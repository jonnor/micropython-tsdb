
# micropython-tsdb

A tiny time-series database / datalake for [MicroPython](https://micropython.org/).

Originally developed together with the [emlearn-micropython project](https://github.com/emlearn/emlearn-micropython) (a Digital Signal Processing and Machine Learning library for MicroPython).

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

## Installing

Install with `mip`.

With mpremote for connected device

    mpremote mip install github:jonnor/micropython-tsdb

On PC for Unix/Windows port

    micropython -m mip install github:jonnor/micropython-tsdb


## Developing

### Running tests on PC

Make sure `micropython` is installed.

Run tests against in-tree tsbd module.

    MICROPYPATH=. micropython tests/test_all.py

## TODO

- Add tests covering MicroDot API
- Cleanup API generally
- Add usage examples.

## Usage

- Insert now data
- Query range
- Insert historical data. Ex import from file
- Chunk deletion
- 
