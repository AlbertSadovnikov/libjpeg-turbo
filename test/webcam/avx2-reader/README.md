# AVX2 32-byte entropy-input scan windows

Implemented and tested 32-byte input checks with amortized window reuse.
Both variants are correct on the validation set, but slower on this CPU and
recording. The scalar bulk reader remains fastest in this comparison.

## Algorithm

An unaligned 256-bit load, `VPCMPEQB` against FF, and `VPMOVMSKB` produce one
mask bit per byte. The first set bit marks the end of the FF-free prefix;
a zero mask means all 32 bytes are clean. The 64-bit reservoir still consumes
six bytes per refill, so a clean window can serve up to five refills.

When six verified bytes remain, an alias-safe eight-byte load supplies the
first six bytes; the last two are discarded. Otherwise another window is
checked. A prefix shorter than six bytes invokes the original stuffing/marker
reader and invalidates the prefix cache. The dispatcher retains the existing
conservative per-block input budget plus 32 additional buffered lookahead
bytes. Short buffers use the general decoder.

- **Local window:** verified-byte count starts at zero for every MCU.
- **Persistent window:** remaining clean bytes carry across successful fast
  MCU calls, resetting at scan initialization, slow-path transitions, and
  failed-fast recovery. Source refills invalidate the prefix cache.

Only `jdhuff.c` is compiled with `-mavx2`. An unmodified Huffman decoder with
the same option is the code-generation control. Other compiler flags stay
unchanged. Production runtime AVX2 dispatch was not added to these prototypes.

## Results

Ryzen 9 3900X, CPU 0, Release, one embedded 1920 x 1080 4:2:2 camera frame.
Five rounds rotate candidate order and bracket each round with baseline runs.
Each case uses 0.2 s minimum measurement and 0.05 s warmup, without low-level
profiling. Values are medians of per-run mean CPU times.

| Variant | BGR ms/frame | Entropy with stores/zeroing ms/frame |
|---|---:|---:|
| Original baseline | 5.9579 | 3.1187 |
| Scalar bulk reader | **5.8943** | **3.0797** |
| Baseline compiled with `-mavx2` | 5.9770 | 3.1321 |
| AVX2 32-byte local window | 6.0773 | 3.2497 |
| AVX2 32-byte persistent window | 6.1206 | 3.2749 |

Local-window median BGR time increases **2.00%**, and entropy time **4.20%**.
Persistent-window times increase **2.73%** and **5.01%**. Both scanners regress
in all five paired BGR comparisons. The compiler-only control is near baseline;
the scalar reader improves all five paired BGR comparisons.

Disassembly confirms YMM byte comparisons and vector movemasks in both scanner
builds. This tests real 32-byte scans reused across refills. Prefix bookkeeping,
register pressure, and vector-to-integer transfer are possible costs, not
isolated hardware-counter findings. Another design may behave differently.

[Raw results](20261028T053428Z/README.md),
[summary JSON](20261028T053428Z/summary.json), and
[validation/instruction evidence](20261028T053428Z/validation.json) are retained.
The scalar reader's earlier 2.47% gain on the full sequence is a separate
workload with its own baseline; these results replay one hot frame.

## Validation

All three new builds pass **333 tests** and pixel comparisons on all 120 camera
frames. Persistent-decoder checks cover five output configurations, table and
geometry changes, and progressive input.

Protected-page tests cover eight JPEGs: 4:2:2, sequential/progressive 4:2:0, and
restart-marker cases. Each source chunk ends before a PROT_NONE page. The 21
chunk sizes include 31/32/33, 2079/2080/2081, and 3103/3104/3105. All hashes
match normal and guarded baseline decoding, including buffer reuse at the same
virtual addresses. This does not replace malformed-input fuzzing or exhaustive
suspension testing.

## Artifacts and reproduction

- [Compiler-only control patch](avx2-codegen.patch)
- [Local-window patch](avx2-32-local.patch)
- [Persistent-window patch](avx2-32-persistent.patch)
- [Source-copy generator](prepare.py)
- [Validation and benchmark runner](run.py)
- [Build commands](build-commands.json)

Patches are alternatives relative to the baseline, not patches to stack. The
working decoder was not changed. Temporary source/build roots are
`/tmp/mjpeg-avx2-reader-src` and `/tmp/mjpeg-avx2-reader-build`.

In a fresh workspace, run `prepare.py`, then configure each variant with
Release, `ENABLE_SHARED=OFF`, `WITH_BENCHMARKS=ON`, and `BUILD=20261024`.
Supply cached Google Benchmark sources through
`FETCHCONTENT_SOURCE_DIR_GOOGLEBENCHMARK` if desired. Build and run CTest, then:

```sh
python3 test/webcam/avx2-reader/run.py
```

The runner also requires `/tmp/mjpeg-google-bench`, the prior scalar build at
`/tmp/mjpeg-entropy-opt-build/bulk-once`, and the captured sequence. It saves
per-run JSON/logs, disassembly, checksums, and validation data in a timestamped
directory.
