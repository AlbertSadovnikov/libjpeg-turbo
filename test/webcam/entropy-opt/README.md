# Entropy refill and lookup-layout experiments

The best result is the scalar [bulk-once.patch](bulk-once.patch): the full
120-frame sequence improved from **6.0900 to 5.9398 ms/frame**, a **2.47% time
reduction**. All three paired trials improved, by 2.39-2.51%. This is a small
gain on this CPU and recording, not a general performance guarantee.

The patch is isolated in `/tmp/mjpeg-entropy-opt-src/bulk-once` and has not been
applied to the working checkout's decoder. It changes only `src/jdhuff.c`.
It has not been combined with the earlier fused AC lookup or BMI experiment.

## Changes tested

| Variant / patch | Change |
|---|---|
| [bulk](bulk.patch) | Bounded eight-byte load, scalar FF detection, byte swap, append six bytes; bounds checked on every refill |
| [compact](compact.patch) | Use 16-bit rather than 32-bit entries in the ordinary eight-bit Huffman lookup |
| [aligned](aligned.patch) | Align the lookup array itself to 64 bytes, keeping the general allocator and field offsets unchanged |
| [compact-aligned](compact-aligned.patch) | Combine entry compaction and lookup alignment |
| [bulk-compact-aligned](bulk-compact-aligned.patch) | Combine the initial reader and both layout changes |
| [bulk-once](bulk-once.patch) | Scalar bulk refill, with the safety budget checked once per MCU |
| [bulk-sse2](bulk-sse2.patch) | Same once-per-MCU budget and bulk append, with SSE2 FF detection instead of scalar detection |

The word reader is enabled only for GNU/Clang x86-64 targets; other targets
retain the byte reader. It uses `memcpy` for an unaligned, alias-safe load,
checks for FF, byte-swaps the loaded word, and appends its first six bytes.
Any FF in the eight-byte lookahead invokes the existing stuffing/marker path.
Checking two extra bytes is conservative.

The refined reader retains the existing conservative 512-byte-per-block input
budget and requires eight additional buffered bytes before entering the fast
MCU decoder. This supplies lookahead headroom without a new bounds check and
end-pointer register at every refill. Short buffers retain the existing slow
path. DC predictors, bitstream parsing, marker processing, and suspension
behavior otherwise use the existing implementation.

The layout check verified that aligned lookups actually have address modulo
64 equal to zero. The ordinary table occupies 1,320 bytes, with a 1,024-byte
lookup at offset 296. Compaction reduces these to 808 and 512 bytes respectively.
See [layout.txt](layout.txt) and the [layout checker](layout.c).

## Measurements

Measurements use Release builds on CPU 0 of the Ryzen 9 3900X, with no low-level
profiling instrumentation. Google Benchmark replays the one embedded camera
frame. Candidate order rotates, and baseline runs bracket each round. The
tables report medians of five per-run mean CPU times. Different experiments
have separate baselines and must be compared within their own table.

The [initial comparison](20261028T043155Z/README.md) found no reliable gain:

| Variant | BGR ms/frame | Entropy with stores/zeroing ms/frame |
|---|---:|---:|
| Baseline | 6.0179 | 3.1495 |
| Initial bulk reader | 6.0280 | 3.2570 |
| Compact lookup | 5.9777 | 3.1939 |
| Aligned lookup | 6.0878 | 3.1905 |
| Compact + aligned | 6.0995 | 3.1826 |
| Initial bulk + compact + aligned | 6.1617 | 3.2839 |

The compact lookup's 0.67% median BGR improvement was inconsistent across
trials; its isolated entropy benchmark regressed. Alignment alone did not
help, despite the verified change in layout. Some trials had transient noise;
raw logs and bracketed baselines are retained.

The [first refined-reader comparison](20261028T044518Z/README.md) measured
0.46% less BGR time and 1.09% less entropy time. A subsequent
[scalar/SSE2 comparison](20261028T045051Z/README.md) measured:

| Variant | BGR ms/frame | Entropy with stores/zeroing ms/frame |
|---|---:|---:|
| Baseline | 6.0697 | 3.1732 |
| Refined scalar reader | 6.0025 | 3.1252 |
| SSE2 detector | 6.1140 | 3.1854 |

The scalar reader reduced these medians by 1.11% and 1.51%. The SSE2 version
did not improve this workload. This measures a specific eight-byte detector;
it does not establish the outcome of a different SIMD scanner/reservoir design.

The [full-sequence confirmation](sequence-confirmation/summary.json) uses the
earlier C replay harness and CLOCK_MONOTONIC wall time, not Google Benchmark.
It preloads all 120 frames, warms up with a complete sequence, reuses output
and decoder state, and measures three passes per process. Each of three rounds
runs baseline, candidate, baseline, giving 1,080 measured candidate decodes and
2,160 baseline decodes. Mean decode times were:

| Build | Mean ms/frame |
|---|---:|
| Baseline | 6.0900 |
| Refined scalar reader | **5.9398** |

The 2.47% reduction is approximately **0.150 ms/frame**. Paired-round reductions
were 2.50%, 2.51%, and 2.39%. The single hot-frame and sequence workloads have
different cache behavior; the percentages are not interchangeable.

## Correctness and input bounds

Every one of the seven variants passed:

- All **333 existing regression/integration tests**, including the embedded
  benchmark's entropy and IDCT stage validations.
- Pixel-for-pixel comparison with baseline for all 120 camera frames.
- Persistent-decoder hash comparisons in BGR, grayscale, half-size output,
  fast-upsample, and fast-IDCT modes, including geometry and Huffman table
  changes and progressive input.
- The [guarded-source test](guarded_source.c), in which each source buffer ends
  immediately before a PROT_NONE page. This covers three camera frames and
  three other JPEGs, with chunk sizes 1, 31, 2047, 2048, 2049, 4095, 4096,
  4097, 8192, and 65536 bytes. Pixel hashes match baseline for every case.

The guard test is Linux-specific and untimed. It exercises chunk refill and
lookahead boundaries; it is not a substitute for malformed-input fuzzing or a
complete input-suspension test campaign. Per-variant CTest logs, validation
JSON, guarded-source CSVs, and benchmark outputs are retained in this directory.

## Reproduce

[prepare.py](prepare.py) creates isolated source copies and saves the patches.
It refuses to overwrite an existing copy. In a fresh temporary workspace:

```sh
python3 test/webcam/entropy-opt/prepare.py --only bulk-once
cmake -S /tmp/mjpeg-entropy-opt-src/bulk-once \
  -B /tmp/mjpeg-entropy-opt-build/bulk-once \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_SHARED=OFF -DWITH_BENCHMARKS=ON \
  -DBUILD=20261024 \
  -DFETCHCONTENT_SOURCE_DIR_GOOGLEBENCHMARK=/tmp/mjpeg-google-bench/_deps/googlebenchmark-src
cmake --build /tmp/mjpeg-entropy-opt-build/bulk-once -j 8
ctest --test-dir /tmp/mjpeg-entropy-opt-build/bulk-once --output-on-failure -j 8
python3 test/webcam/entropy-opt/run.py --variants bulk-once
```

The runner expects the original embedded-frame build at
`/tmp/mjpeg-google-bench` and the saved camera sequence. The candidate's CTest
run creates the other JPEG fixtures used for validation. The full-sequence
confirmation CSVs and summary record the separate replay measurement.

Next substantial experiments would be a different reservoir representation or
decoding multiple MCUs while keeping entropy state live. Neither was implemented
here. Ordinary cache-line alignment is not a demonstrated bottleneck in these
measurements; padding the remaining decoder structures is not the next priority.
