
"""
Benchmarks for delta_simple9 storage
"""

import time
import array
import os
import sys

from tsdb import delta_simple9 as tc

def check(cond, msg):
    if not cond:
        raise AssertionError(msg)

def _ms():
    try: return time.ticks_ms()
    except AttributeError: return int(time.time() * 1000)

def _diff(t):
    try: return time.ticks_diff(time.ticks_ms(), t)
    except AttributeError: return int(time.time() * 1000) - t

def bench_encode_1000_rows():
    """Benchmark write_rows: 1000 rows, 2 cols, repeated 20x."""
    d = array.array('h')
    for i in range(1000): d.append(i % 30000); d.append((i+1) % 30000)
    w = tc.Writer('/tmp/bench_enc.des9', 2, 128)
    t = _ms()
    for _ in range(20):
        w.write_rows(d)
    elapsed = _diff(t)
    w.close()
    os.remove('/tmp/bench_enc.des9')
    rows_per_ms = 20000 / elapsed if elapsed else 0
    print("  bench_encode: 20x1000 rows in {}ms  ({:.0f} rows/ms)".format(elapsed, rows_per_ms))
    check(elapsed < 5000, "encode too slow: {}ms".format(elapsed))

def bench_decode_1000_rows():
    """Benchmark read_chunk_into: decode 1000 rows, 2 cols, repeated 20x."""
    d = array.array('h')
    for i in range(1000): d.append(i % 30000); d.append((i+1) % 30000)
    with tc.Writer('/tmp/bench_dec.des9', 2, 128) as w:
        w.write_rows(d)
    buf = array.array('h', [0] * (128 * 2))
    t = _ms()
    for _ in range(20):
        with tc.Reader('/tmp/bench_dec.des9') as r:
            while r.read_chunk_into(buf): pass
    elapsed = _diff(t)
    os.remove('/tmp/bench_dec.des9')
    rows_per_ms = 20000 / elapsed if elapsed else 0
    print("  bench_decode: 20x1000 rows in {}ms  ({:.0f} rows/ms)".format(elapsed, rows_per_ms))
    check(elapsed < 5000, "decode too slow: {}ms".format(elapsed))

def bench_struct_unpack():
    """Benchmark struct.unpack patterns: per-word vs bulk."""
    import struct
    raw = bytes(range(256)) * 16  # 4096 bytes = 1024 uint32 words
    n   = 1024

    # Per-word unpack (current approach)
    t = _ms()
    for _ in range(100):
        for wi in range(n):
            struct.unpack('<I', raw[wi*4:wi*4+4])
    t_per_word = _diff(t)

    # Bulk unpack
    fmt = '<{}I'.format(n)
    t = _ms()
    for _ in range(100):
        struct.unpack(fmt, raw[:n*4])
    t_bulk = _diff(t)

    print("  struct.unpack 1024 words x100: per-word={}ms  bulk={}ms  speedup={:.1f}x".format(
        t_per_word, t_bulk, t_per_word/t_bulk if t_bulk else 0))

def bench_decode_detail():
    """Break down decode cost per chunk."""
    import struct

    # Build a real file with 256 rows, 7 cols
    n_rows, n_cols = 256, 7
    d = array.array('h')
    for i in range(n_rows):
        for c in range(n_cols): d.append((i + c*100) % 30000)

    path = '/tmp/bench_detail.des9'
    with tc.Writer(path, n_cols, n_rows) as w:
        w.write_rows(d)

    decode_buf = array.array('h', [0] * (n_rows * n_cols))
    N = 200  # iterations

    # Full decode (open + read_chunk_into + close)
    t = _ms()
    for _ in range(N):
        r = tc.Reader(path)
        r.read_chunk_into(decode_buf)
        r.close()
    t_full = _diff(t)

    # Just file open + read raw bytes + close (no decode)
    import os
    fsize = os.stat(path)[6]
    t = _ms()
    for _ in range(N):
        f = open(path, 'rb')
        f.read(fsize)
        f.close()
    t_raw_io = _diff(t)

    # Just struct.unpack (simulated: unpack n_cols * n_words words)
    # Estimate ~20 words per col per chunk
    n_words = n_cols * 20
    raw = bytes(range(128)) * ((n_words * 4 // 128) + 1)
    fmt = '<{}I'.format(n_words)
    t = _ms()
    for _ in range(N):
        struct.unpack(fmt, raw[:n_words * 4])
    t_unpack = _diff(t)

    # Just the bit-extraction inner loop (worst case: 28 words, 1 val each)
    words = struct.unpack('<28I', bytes(range(112)))
    dst = array.array('h', [0] * (n_rows * n_cols))
    t = _ms()
    for _ in range(N):
        prev = 0; idx = 0
        for word in words:
            v = word & 0x1FFFF
            prev += (v >> 1) ^ -(v & 1)
            dst[idx] = prev; idx += 1
    t_bits = _diff(t)

    # Array slice allocation
    t = _ms()
    for _ in range(N):
        array.array('h', decode_buf[0 : n_rows * n_cols])
    t_slice = _diff(t)

    os.remove(path)
    print("  decode_detail x{} ({}rows {}cols):".format(N, n_rows, n_cols))
    print("    raw_io={}ms  full_decode={}ms  unpack={}ms  bits={}ms  slice={}ms".format(
        t_raw_io, t_full, t_unpack, t_bits, t_slice))
    print("    decode overhead vs raw IO: {:.1f}x".format(t_full / t_raw_io if t_raw_io else 0))


def bench_readinto_vs_read():
    """Compare readinto(buf,n) vs read(n) and struct.unpack_from vs unpack."""
    import struct
    N = 1000

    path = '/tmp/bench_rio.bin'
    data = bytes(range(256)) * 40  # 10240 bytes
    with open(path, 'wb') as f:
        f.write(data)

    buf6  = bytearray(6)
    buf1k = bytearray(1024)

    # readinto(buf, n) — header size
    t = _ms()
    for _ in range(N):
        f = open(path, 'rb')
        for _ in range(14):  # 7 cols * 2 reads each
            f.readinto(buf6, 6)
        f.close()
    t_readinto_hdr = _diff(t)

    # readinto(buf, n) — data size (~140 bytes typical)
    t = _ms()
    for _ in range(N):
        f = open(path, 'rb')
        for _ in range(7):
            f.readinto(buf1k, 140)
        f.close()
    t_readinto_dat = _diff(t)

    # read(n) — for comparison
    t = _ms()
    for _ in range(N):
        f = open(path, 'rb')
        for _ in range(14):
            f.read(6)
        f.close()
    t_read_hdr = _diff(t)

    # struct.unpack_from vs unpack
    t = _ms()
    fmt = '<hHH'
    for _ in range(N * 7):
        struct.unpack_from(fmt, buf6)
    t_upk_from = _diff(t)

    t = _ms()
    for _ in range(N * 7):
        struct.unpack(fmt, bytes(buf6))
    t_upk = _diff(t)

    # open+close cost alone
    t = _ms()
    for _ in range(N):
        f = open(path, 'rb')
        f.close()
    t_open = _diff(t)

    os.remove(path)
    print("  readinto_hdr(6)x14 x{}: {}ms  ({:.1f}ms/chunk)".format(N, t_readinto_hdr, t_readinto_hdr/N))
    print("  readinto_dat(140)x7 x{}: {}ms  ({:.1f}ms/chunk)".format(N, t_readinto_dat, t_readinto_dat/N))
    print("  read(6)x14         x{}: {}ms  ({:.1f}ms/chunk)".format(N, t_read_hdr, t_read_hdr/N))
    print("  unpack_from x{}:    {}ms".format(N*7, t_upk_from))
    print("  unpack      x{}:    {}ms".format(N*7, t_upk))
    print("  open+close  x{}:    {}ms  ({:.1f}ms/op)".format(N, t_open, t_open/N))


def bench_encode_detail():
    """Break down encode cost: zigzag vs selector search vs file write."""
    import struct
    d = array.array('h')
    for i in range(1000): d.append(i % 30000); d.append((i+1) % 30000)
    win  = array.array('I', [0] * 28)
    wbuf = array.array('I', [0] * 128)

    # Just the zigzag+delta loop (window fill only, no selector)
    t = _ms()
    for _ in range(100):
        prev = d[0]
        pending = 0
        for i in range(0, len(d), 2):  # col 0, stride 2
            dv = d[i] - prev
            prev = d[i]
            win[pending % 28] = ((dv << 1) ^ (dv >> 16)) & 0x1FFFF
            pending += 1
    t_zigzag = _diff(t)

    # Just struct.pack calls (header writes)
    t = _ms()
    hdr = struct.pack('<hHH', 0, 20, 128)
    for _ in range(100):
        for _ in range(8 * 2):  # 8 chunks * 2 cols
            struct.pack('<hHH', 0, 20, 128)
    t_pack = _diff(t)

    # Just bytes() conversion
    t = _ms()
    for _ in range(100):
        for _ in range(16):  # 8 chunks * 2 cols
            bytes(wbuf[:20])
    t_bytes = _diff(t)

    print("  encode detail x100: zigzag_loop={}ms  struct_pack={}ms  bytes_conv={}ms".format(
        t_zigzag, t_pack, t_bytes))


TESTS = [
    bench_struct_unpack,
    bench_encode_1000_rows,
    bench_decode_1000_rows,
    bench_decode_detail,
    bench_readinto_vs_read,
]

def main():
    passed = failed = 0
    for t in TESTS:
        try:
            t()
            print("  OK:", t.__name__)
            passed += 1
        except Exception as e:
            print("FAIL:", t.__name__, "-", e)
            failed += 1

    print("\n{}/{} passed".format(passed, passed+failed))
    if failed:
        sys.exit(1)

if __name__ == '__main__':
    main()


