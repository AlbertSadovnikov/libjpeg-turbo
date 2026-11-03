# Overall JPEG → NV12: LTO, no PGO

**Current comparison policy: no PGO anywhere in either codec. LTO is enabled
and matched.** Earlier PGO-assisted cohorts, including `../overall/`, are
historical and excluded from these headline numbers.

## Result

Ryzen 9 3900X, CPU 0, 1920×1080 4:2:2 webcam capture:

| Complete CPU JPEG → NV12 | ms/frame | Frames/s, reciprocal latency |
|---|---:|---:|
| Stock TurboJPEG fast IDCT + AVX2 NV12 pack | 4.533 | 221 |
| Current optimized pipeline | 3.354 | 298 |

**26.0% less latency**, saving 1.179 ms/frame, or **1.35× throughput**
(+35.2%). All five stock/current/stock brackets improve, ranging 25.24–26.47%.
These are directly measured overall comparisons, not compounded percentages
from earlier incremental experiments. Raw rounds and binary hashes are in
`results.json` and `summary.json`.

Fast Y is used in both. The candidate retains the previously documented
reduced-chroma approximation, so this is **not a byte-identical comparison
against stock UV**. It introduces no further output change relative to the
established candidate contract. GPU upload and encoding are not measured.

## Build and audit

Both complete codec archive sets are freshly rebuilt from source using
Clang 18 with identical `-O3 -DNDEBUG -mtune=znver2 -flto=thin` flags. Both
entropy translation units additionally use `-mbmi2`; CPU feature tiers match.
Stock `src/` and `simd/` are unmodified production sources in an isolated
snapshot. Current uses the source prototype with the bulk reader, pair10 LUT,
shifted thresholds, precomputed span and guarded inline AVX2 MCU clearing.
Every codec C object is rebuilt; no retained PGO-trained member is reused.

Both application drivers and the shared fusion wrapper are freshly compiled
with GCC O3, native code, without PGO. This preserves the established UV
floating-point rounding; compiling that wrapper with Clang changed a few UV
bytes in prior validation. The same driver compiler/optimization policy
applies on both sides. Paired register-rewritten Y and exact-chroma NASM
objects are reassembled. Google Benchmark support is a shared native GCC O3
archive whose build flags contain no profiling. No old codec archive enters
the new link. LTO describes the codec C objects, not the NASM/native support.

`audit.py` checks every archive member: LLVM bitcode has neither
`ProfileSummary` metadata nor instrumentation intrinsics/sections. Compile
commands are checked for LTO and absence of profile flags; final binaries
contain no LLVM profiling runtime symbols. The full audit is retained in
`no-pgo-audit.json`, not inferred solely from the final link command.

No profile generation/use/sample flags, training phase or profile files are
used by these scripts. First 30 frames remain excluded from timing for
continuity with prior experiments, although this cohort has no PGO training.

## Validation and measurement

Stock output on all 120 captures matches its saved raw/planar/scalar packing
correctness oracle, including strided/padded output. Current output matches
its saved full NV12 reports on all 120 captures, six fixtures (`rst1`,
`optimized`, `progressive`, `dense`, `tail63`, `zeroac`), and a mixed sequence
with changed quantizer/Huffman tables and returns to previous tables. Both
IDCT modes and output padding are checked. Historical outputs are correctness
oracles only; no historical PGO binary is run or timed.

CPU 0, five stock/current/stock brackets, 90 preloaded held-out frames,
six measured passes after a complete warmup per process. Loading, allocation
and hashing are outside clocks. Stock separates decode/packing with one extra
clock read; both are included in its total. Processes run sequentially, with
no concurrent compilation/verification. CPU frequency is not fixed. This is
one scene and one CPU, not a portability guarantee. FPS is reciprocal mean
CPU decode/output latency, not measured GPU/encoder or multicore throughput.

## Reproduction and selection

```
python3 test/webcam/nv12/lto-only/build.py
python3 test/webcam/nv12/lto-only/audit.py
python3 test/webcam/nv12/lto-only/run.py
python3 test/webcam/nv12/lto-only/select.py
```

Selected executable: `/tmp/mjpeg-lto-only/nv12`. Archives and executable are
also under `/tmp/mjpeg-lto-only/candidate/`. `preferred-candidate.json` records
the no-PGO policy and exact hashes. The quantizer cache remains excluded.
Older experiment binaries remain available for historical reproduction, but
must not be used for new headline comparisons.

Requires retained prototype source/wrapper, capture, fixtures and benchmark
support listed in `../NEXT_EXPERIMENTS.md`. New codecs, native support, logs
and snapshots stay under `/tmp/mjpeg-lto-only`. `codec.patch` records source
differences against the isolated stock snapshot. Production repository
`src/` and `simd/` are unchanged. No commit or push.
