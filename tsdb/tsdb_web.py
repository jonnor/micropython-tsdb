"""
microhive_api.py - HTTP API for MicroHive using Microdot

Endpoint:
    GET /query?resource=<n>&start=<epoch_s>&end=<epoch_s>[&chunk_rows=<n>]

Returns the query result as a streaming .npy file (application/octet-stream).
The .npy header is written directly (no npyfile.Writer dependency) and data
chunks are streamed as raw bytes, one per get_timerange yield.

MicroPython note:
    Async generator functions (async def + yield) are not supported in MicroPython.
    Streaming uses a class-based generator compatible with both platforms.
"""

import os
import struct
import asyncio
import time
import array

# ---------------------------------------------------------------------------
# Minimal .npy header writer (little-endian int16, C order, 2D)
# Avoids needing npyfile.Writer to accept a file-like object.
# ---------------------------------------------------------------------------

def _npy_header(n_rows, n_cols):
    """Return .npy v1.0 header bytes for a (n_rows, n_cols) int16 array."""
    descriptor = "{'descr': '<i2', 'fortran_order': False, 'shape': (%d, %d), }" % (n_rows, n_cols)
    # Total = 10 bytes fixed prefix + descriptor + '\n', padded to multiple of 64
    desc_bytes = descriptor.encode('latin-1')
    total = 10 + len(desc_bytes) + 1
    pad = (64 - (total % 64)) % 64
    desc_bytes = desc_bytes + b' ' * pad + b'\n'
    return b'\x93NUMPY\x01\x00' + struct.pack('<H', len(desc_bytes)) + desc_bytes

# ---------------------------------------------------------------------------
# Sync class-based generator — MicroPython compatible streaming response
# ---------------------------------------------------------------------------

class _NpyStreamGenerator:
    """
    Streams a MicroHive query result as a .npy file, one bytes chunk per yield:
      - First yield: .npy header (shape + dtype descriptor)
      - Subsequent yields: raw int16 bytes for each chunk_rows block of data
    """

    def __init__(self, db, resource, start_s, end_s, chunk_rows, n_cols, hop_us):
        ...

    def __iter__(self):
        return self

    def _build_iter(self):
        total_rows = int((self._end_s - self._start_s) * 1_000_000) // self._hop_us

        # First chunk: .npy header
        yield _npy_header(total_rows, self._n_cols)

        # Subsequent chunks: raw bytes per query chunk
        gen = self._db.get_timerange(self._resource, self._start_s, self._end_s, chunk_rows=self._chunk_rows):
        for chunk in gen:
            yield bytes(chunk)

    def __next__(self):
        if self._iter is None:
            self._iter = self._build_iter()
        try:
            return next(self._iter)
        except StopIteration:
            raise

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def add_routes(app, db):
    """Register TSDB routes on an existing Microdot app."""

    @app.get('/info')
    async def info(request):
        print('info hit')
        resource = request.args.get('resource')
        if not resource:
            return 'Missing resource', 400
        if resource not in db._resources:
            return 'Unknown resource: {}'.format(resource), 404
        info = db.get_info(resource)
        if info['n_partitions'] == 0:
            return {'resource': resource, 'has_data': False}, 200
        return {
            'resource':     resource,
            'has_data':     True,
            'start':        info['start_s'],
            'end':          info['end_s'],
            'n_partitions': info['n_partitions'],
            'granularity':  info['granularity'],
            'columns':      info['columns'],
            'hop_us':       info['hop_us'],
        }, 200

    @app.get('/query')
    async def query(request):

        from microdot import Response

        resource   = request.args.get('resource')
        start_s    = request.args.get('start')
        end_s      = request.args.get('end')
        chunk_rows = int(request.args.get('chunk_rows', '600'))

        if not resource or not start_s or not end_s:
            return 'Missing resource, start or end', 400

        try:
            start_s = int(start_s)
            end_s   = int(end_s)
        except ValueError:
            return 'start and end must be integer epoch seconds', 400

        if resource not in db._resources:
            return 'Unknown resource: {}'.format(resource), 404

        cfg    = db._resources[resource]
        n_cols = len(cfg['columns'])
        hop_us = cfg['hop']

        gen = _NpyStreamGenerator(db, resource, start_s, end_s,
                                  chunk_rows, n_cols, hop_us)
        r = Response(gen, 200, {
            'Content-Type': 'application/octet-stream',
            'Content-Disposition': 'attachment; filename="{}.npy"'.format(resource),
        })
        return r


