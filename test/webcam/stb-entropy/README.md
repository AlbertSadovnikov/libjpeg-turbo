# stb-inspired entropy experiments

2026-10-31, Ryzen 9 3900X, GCC 13.3 release builds, CPU 0. Embedded webcam
frame: 1920x1080 baseline 4:2:2, 371,718 bytes. Production decoder sources are
unchanged. Reference header: `extra/stb_image.h` v2.30, provenance in
`extra/README.md`.

## Variants

- **Original:** unmodified libjpeg-turbo.
- **Scalar:** previously validated scalar bulk reservoir reader.
- **Pair10:** current winner, scalar refill plus branchless two-symbol AC LUT,
  8-byte entries, 8 KiB per AC table, persistent table cache.
- **Compact9:** stb-style single-symbol/value fusion, 9-bit lookahead, two-byte
  entries. Packs signed 8-bit amplitude, 4-bit zero run, 4-bit consumed length.
  1 KiB per table. Uses scalar refill and persistent caching for comparison;
  this ports the LUT idea into our decoder, not the entire stb implementation.
- **Compact-pair10:** 4-byte pair entries, 4 KiB per table. Two signed 8-bit
  values, two 4-bit runs, one pair flag, 4-bit consumed length. Singles repeat
  the store as in pair10; amplitudes outside -128..127 fall back. This tests
  the packed representation, whose extraction costs differ from pair10.
- **Threshold-pair10:** unchanged pair LUT plus stb-style pre-shifted exclusive
  maximum-code thresholds. One 16-bit candidate is compared against successive
  thresholds instead of extending the candidate one bit at a time. Append 18
  unsigned thresholds (72 bytes) to each derived table, including a sentinel.
  This also changes derived-table allocation size; there is no separate
  allocation-layout-only control. Do not attribute every saved cycle solely
  to fewer bit operations.
- **stb:** actual stb decoder, using its internal native component planes and
  our same AVX2 vertical box filter/interleave. Includes upstream-style per-frame
  table construction, component allocation/free and a Y-plane copy. No RGB
  round trip. This is an experimental internal-API adapter, not stb's public
  API, and not a pure entropy comparison. It is enabled only when compiling
  `nv12_bench.cc` with `MJPEG_STB_REFERENCE`; normal targets do not include stb.

The existing pair LUT already includes all single-symbol/value sequences that
the compact 9-bit table could cover. Adding it as a fallback to that unchanged
table would be redundant except around rejected block-boundary pairs; these
experiments therefore test compact entries directly instead.

## Main comparison

Five rounds, rotating/reversing variant order. Median of Google Benchmark
per-run CPU means, 0.2 s minimum time and 0.03 s warmup per case. Separate
100-frame entropy measurements and five decode-only PMU rounds follow native
runs. User events: cycles, instructions, branches, branch misses; all run at
100%, no multiplexing. Warmup/setup excluded from PMU aggregation using an
acknowledged perf FIFO. CPU frequency is not fixed.

| Variant | Accurate raw-strip NV12 ms | Fast-IDCT raw-strip NV12 ms | Entropy cycles/frame |
|---|---:|---:|---:|
| Original | 5.1189 | 4.5936 | 13.867M |
| Scalar | 4.9757 | 4.4803 | 13.356M |
| Pair10 | 4.4724 | 4.0615 | 11.007M |
| Compact9 | 5.1223 | 4.8542 | 14.198M |
| Compact-pair10 | 4.5514 | 4.1625 | 11.728M |
| Threshold-pair10 | 4.4547 | 4.0059 | 10.956M |
| Actual stb native planes to NV12 | 8.3524 | not applicable | not measured separately |

Compact9 uses about 29.0% more entropy cycles than pair10; compact-pair10 uses
about 6.6% more. Both are slower in all five paired entropy-counter rounds.
Smaller LUTs do not automatically help: compact-pair10 executes 24.285M entropy
instructions vs 21.250M for pair10, and more branches/mispredictions. These
measurements do not prove a single cause for the regressions.

Threshold-pair10 has 20.958M entropy instructions, 2.816M branches and 163,694
branch misses vs pair10's 21.250M / 2.752M / 166,350. Median entropy cycles fall
0.46%, with improvement in four of five paired trials. Whole-frame native
timings have outliers; their initial small differences motivated a separate
fixed-frame full-NV12 confirmation rather than relying on this table alone.

stb does not produce identical IDCT results. Against accurate libjpeg NV12:
Y max absolute difference 1, mean 0.001973, 0.197% of samples changed; combined
UV max 1, mean 0.000367, 0.037% changed. Scalar and SIMD packing match exactly
within stb. Its full-decoder result is very close in pixels, but architectural
differences prevent interpreting its 8.35 ms as an entropy-only comparison.

## Fixed-frame NV12 confirmation

Five alternating paired trials, 100 frames per trial after five warmups.
Native runs first, then gated hardware runs. Both variants use identical
raw-strip decode/AVX2 packing. The driver is fixed to the embedded 1920x1080
4:2:2 fixture. Hashes cover the complete NV12 output and match for each IDCT
mode. Hardware-run wall times include FIFO waits and are not used as latency.

| Mode | Pair10 native ms | Threshold native ms | Time reduction | Cycle reduction |
|---|---:|---:|---:|---:|
| Accurate | 4.4728 | 4.4084 | 1.44% | 1.36% |
| Fast IDCT | 4.1168 | 4.0084 | 2.63% | 3.04% |

Both native time and hardware cycles improve in all five pairs for each mode.
Accurate paired cycle reductions range 0.16–2.60%, fast 2.32–3.57%. This is a
small useful additional win on this fixture/CPU, not a guaranteed improvement
on every JPEG or a measured NV12 throughput gain across the 120-frame sequence.
The size difference between isolated entropy and full-decode gains may involve
loop/layout/cache interactions; aggregate counters do not identify the cause.

Raw values and trial records: `summary.json`, `results.json`, and
`confirmation/summary.json`. Per-run benchmark files, logs, CSVs and binaries
remain local. Repeated one-frame native times should be compared within the
same experiment, not directly with earlier sessions.

## Correctness

All three ported variants passed 332 CTest tests each, byte-identical decoded
pixels against the original for all 120 webcam frames, a persistent decoder
in five modes across mixed baseline/progressive frames, and protected-page
source chunks (five images, ten chunk sizes). The NV12 executable checks each
variant's scalar/SIMD and planar/raw-strip equality, independent plane strides
and padding guards, for accurate and fast IDCT. These exact-equality claims
apply to the ported libjpeg variants, not the different stb IDCT.

The long-code change is confined to the existing fast baseline Huffman macro;
the slow/suspending path remains unchanged. It restores the speculative bit
drop before inspecting 16 bits, uses an exclusive 17-bit sentinel, and retains
the original invalid-code 17-bit consumption behavior. This remains a
prototype, not a substitute for a production malformed-input/fuzz audit.

## Reproduce

Requires the earlier original/scalar/pair10 builds and Google Benchmark under
`/tmp` as recorded in `test/webcam/nv12/run.py`.

```sh
python3 test/webcam/stb-entropy/prepare.py
python3 test/webcam/stb-entropy/build.py
python3 test/webcam/stb-entropy/run.py
python3 test/webcam/stb-entropy/confirm.py
```

The prepare script refuses to overwrite existing variant source directories.
Each retained `.patch` is self-contained against the original codec and
includes scalar refill and the necessary persistent cache support. In
particular `threshold-pair10.patch` includes the current pair10 winner plus
the threshold change; do not apply it on top of the pair patch.
