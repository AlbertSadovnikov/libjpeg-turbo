# MJPEG decoding speedup investigation

Updated 2026-10-28. Measurements use libjpeg-turbo 3.2.1 at commit
`36956793b60deb2d1169d1432be6d19871f5ecb1`, on an AMD Ryzen 9 3900X
(Zen 2), with GCC 13.3, Release optimization (`-O3 -DNDEBUG`), and SIMD enabled.
The pre-existing `cmake-build-debug` build is Debug and was not used for these
performance conclusions.

Full-resolution webcam JPEG decoding to BGR takes approximately **6 ms/frame**
on one CPU core, or about **166 fps**. A new scalar-bulk plus branchless
two-AC-symbol lookup prototype reaches **5.450 ms/frame** across all 120
frames: **10.17% less time than its original control**, **9.42% less than its
scalar-bulk control**. On the embedded fixture, entropy cycles fall **16.90%**
versus scalar bulk. See the [multi-symbol experiment](test/webcam/multisymbol/README.md).
All changes remain isolated prototypes, with patches retained.

Earlier, a refined scalar bulk bit reader saved
**2.47% of full-sequence decode time** in its confirmation run. A persistent
combined AC-symbol/amplitude lookup saved **1.86%** in a separate experiment.
Compiler-generated BMI1/BMI2 instructions
alone, cache-line alignment, and the tested SSE2/AVX2 byte detectors produced no
consistent gain. Larger savings came from changing output resolution/format
or choosing less accurate reconstruction algorithms.

Each experiment below has its own contemporary baseline. Compare variants
within their experiment; differences between separate baseline runs reflect
run-to-run variation. All results concern this CPU and one recorded scene.

The capture and measurement setup
---------------------------------

Captured from a Logitech Webcam C930e, `/dev/video0`, without changing its
settings or re-encoding its output:

- 120 consecutive frames after discarding 30 startup frames.
- 1920 x 1080, baseline 8-bit JPEG, YCbCr **4:2:2**.
- Observed 29.9286 fps; no device-sequence gaps.
- 44,164,213 compressed bytes total, about 368 KB/frame on average.
- All frames decode without warnings.
- All 120 frames have identical Huffman tables, quantization tables, sampling
  factors, dimensions, scan layout, and a zero restart interval.
- Each frame has a 702-byte header. All complete JPEG files are distinct.

The [capture directory](test/webcam/20261023T230418Z/) contains the original
`capture.mjpg`, individual `frame_000000.jpg` through `frame_000119.jpg`, camera
settings, capture diagnostics, and a [manifest](test/webcam/20261023T230418Z/manifest.json)
with timestamps, byte offsets, sizes, and SHA-256 hashes. Frame boundaries were
taken from the logged V4L2 buffer sizes; the JPEGs exactly reconstruct the stream.

Sequence benchmarks preload every JPEG into memory, reuse one decompressor and
output buffer, and decode the entire sequence once for warmup before measured
passes. Per-frame timings use `CLOCK_MONOTONIC`. Processes are pinned to CPU 0.
Capture, USB transfer, disk I/O, and frame-queue delays are excluded. These are
warm replay measurements, not capture-to-consumer latency measurements.

The harness uses the libjpeg decompression API and the same underlying decoding
path used by TurboJPEG. The earlier exploratory measurements used `tjbench`.

Normal decoding and output choices
---------------------------------

Three trials of three measured passes over all frames: 1,080 timed decodes
per configuration. Fast upsampling and fast IDCT were tested separately.

| Configuration | Mean ms/frame | p95 ms/frame | FPS | Time reduction |
|---|---:|---:|---:|---:|
| Default BGR, 1920 x 1080 | 6.026 | 6.132 | 165.9 | Baseline |
| Ordinary Huffman lookahead enlarged from 8 to 10 bits | 6.045 | 6.191 | 165.4 | No benefit |
| Fast chroma upsampling | 5.569 | 5.675 | 179.6 | 7.6% |
| Fast IDCT | 5.522 | 5.616 | 181.1 | 8.4% |
| Decode directly to 960 x 540 | 4.510 | 4.644 | 221.7 | 25.2% |
| Grayscale output | 4.208 | 4.299 | 237.6 | 30.2% |
| BGR with SIMD disabled | 13.317 | 13.645 | 75.1 | Slower |

Default BGR p99 latency was 6.474 ms. Fast upsampling and fast IDCT change
reconstruction accuracy; grayscale and half-size output change what the
consumer receives. Half-size decoding still parses the compressed coefficient
stream, explaining why quartering the output pixel count does not quarter time.

See the [report](test/webcam/20261023T230418Z/timings-20261023T231616Z/README.md)
and [summary JSON](test/webcam/20261023T230418Z/timings-20261023T231616Z/summary.json).

Where decoding time goes
------------------------

The pipeline is header parsing/setup, entropy decoding into quantized 8x8
coefficient blocks, dequantization plus IDCT, chroma upsampling, and color
conversion/output. Entropy decoding and IDCT are interleaved by MCU; API-call
timings alone cannot separate them. Dequantization is integrated into IDCT.

The existing `WITH_PROFILE=ON` instrumentation measured:

| Instrumented stage | Mean ms/frame |
|---|---:|
| Entropy decoding | 3.4695 |
| Dequantization + IDCT | 2.8173 |
| Chroma upsampling | 0.3657 |
| Color conversion | 0.7139 |
| Other work and timing overhead | Approximately 2.69 |
| **Instrumented total** | **10.0592** |

Instrumentation raises total time from approximately 6.03 to 10.06 ms. These
stage costs are a bottleneck guide, not a precise partition of normal latency.
The remaining time includes useful controller/buffer work and instrumentation
overhead; coefficient-buffer zeroing is outside the entropy timer. The
profiler's Mcoefficients/sec metric counts coefficient slots, including implicit
zeros, rather than actual Huffman symbols.

In the normal build, header parsing averaged **1.51 microseconds**, startup
**3.38 microseconds**, and finish/cleanup **0.41 microseconds**. Together these
are approximately **0.09%** of total decode time, leaving little direct benefit
from eliminating setup alone.

Huffman decoder findings and reuse opportunities
------------------------------------------------

The scalar decoder handles a DC difference, followed by AC run/size symbols,
amplitude bits, sign conversion, and stores in natural coefficient order.
Each decoded symbol determines where the next symbol starts. Scaling or
discarding chroma does not generally allow skipping its entropy-coded symbols.

There are two separate fast/fallback mechanisms:

- An 8-bit symbol lookup handles short Huffman codes; longer codes are resolved
  with additional comparisons, including inside the fast MCU routine.
- `decode_mcu_fast()` uses simplified input handling. Restart intervals disable
  it for the entire scan. It also requires sufficient buffered input: a
  conservative 512 bytes per block, or 2,048 bytes for this camera's four-block
  4:2:2 MCU. Near boundaries it uses the general decoder.

The 64-bit fast reader appends six input bytes at a time through individual
byte checks. An entropy-data `FF 00` pair represents a literal `FF` byte.
Bit-reservoir state and DC predictors must start fresh for every frame.

Three representative camera frames each contain 64,800 DC symbols and about
500,000 AC symbols. Approximately 2.5% of AC codes exceed eight bits and 0.54%
exceed ten bits. Most symbols already use the short-code lookup.

Reusing the decoder handle preserves permanent state, including the original
JPEG table objects, but `jpeg_finish_decompress()` frees per-image allocations.
Derived Huffman lookups, IDCT multiplier tables, and internal buffers are
normally recreated. A stream context could retain them, but measured setup
cost is tiny. A more useful role for reuse is amortizing construction of a
specialized decoding structure that reduces the inner-loop work.

We also compared all 64 quantized coefficients at corresponding block
positions across all 119 adjacent frame pairs:

| Component | Exactly unchanged blocks |
|---|---:|
| Luminance Y | 1.10% |
| Chroma Cb | 6.01% |
| Chroma Cr | 7.72% |
| Overall | 3.98% |

Because quantization tables are unchanged, identical coefficient blocks could
reuse IDCT output. Only about 4% of IDCT calls would be skipped here, while
coefficient comparison and retained buffers add work. Entropy decoding is
still needed to establish equality. Exact temporal block reuse therefore
looks unattractive for this recording. See the
[comparison counts](test/webcam/20261023T230418Z/timings-20261023T231616Z/block-reuse.txt).

Persistent combined AC lookup experiment
----------------------------------------

Implemented in an isolated source copy. A lookup returns the zero run, signed
amplitude, and total consumed bits together when the complete token fits.
It handles EOB/ZRL and falls back to the existing decoder for longer tokens.
Caches live in the permanent pool, compare Huffman table contents before reuse,
and rebuild when those contents change. Only two tables were built across the
entire 120-frame camera sequence.

Five trials of three measured passes: 1,800 timed decodes per variant, with
rotated variant order and no low-level profiling instrumentation.

| Variant | Mean ms/frame | p95 ms/frame | Time reduction |
|---|---:|---:|---:|
| Contemporary baseline | 6.1077 | 6.4513 | Baseline |
| Combined 10-bit lookup | **5.9938** | 6.1986 | **1.86%** |
| Combined 11-bit lookup | 6.0196 | 6.3210 | 1.44% |
| Combined 12-bit lookup | 6.1084 | 6.4263 | No benefit |

The 10-bit variant improved all five trial means, by 1.06-2.93%, saving
approximately 0.114 ms/frame overall. Its two lookup arrays occupy 8 KiB total,
plus metadata. The 11- and 12-bit arrays occupy 16 and 32 KiB respectively;
broader coverage did not yield a better overall result.

All camera frames match pixel-for-pixel for all widths. Persistent-decoder
hash checks cover table changes, geometry changes, progressive/restart frames,
and five output configurations. All **332 existing regression tests pass**
for the 10-bit build. This remains an experimental patch; malformed-input
fuzzing and broader hardware/scene coverage have not been performed.

Artifacts: [patch](test/webcam/fused-ac/fused-ac.patch),
[notes](test/webcam/fused-ac/README.md),
[results](test/webcam/fused-ac/20261023T233210Z/README.md), and
[summary JSON](test/webcam/fused-ac/20261023T233210Z/summary.json).

Huffman-only BMI1/BMI2 experiment
--------------------------------

Enabled `-mbmi -mbmi2` exclusively for `src/jdhuff.c`. GCC automatically emitted
20 SHLX, 18 SHRX, and one BZHI instruction; the generic baseline Huffman object
contained none of the checked BMI instructions. These are static counts.

For exact isolation, each benchmark archive was copied from the original
baseline and only `jdhuff.c.o` was replaced. All other archive members match
byte-for-byte. This also avoids NASM source-path metadata differences between
build directories.

Five alternating trials of three measured passes: 1,800 timed decodes per build.

| Build | Mean ms/frame | Median ms/frame | p95 ms/frame |
|---|---:|---:|---:|
| Contemporary baseline | 6.0863 | 6.0645 | 6.2609 |
| Huffman-only BMI1/BMI2 | 6.1018 | 6.0592 | 6.4234 |

Two trial means improved and three regressed. The 0.25% mean regression and
nearly identical medians show **no consistent benefit** from these compiler
flags alone. Every camera frame matches pixel-for-pixel, persistent-decoder
checks pass in five output configurations, and all **332 regression tests pass**.

Artifacts: [CMake patch](test/webcam/bmi2/source-options.patch),
[notes](test/webcam/bmi2/README.md),
[results](test/webcam/bmi2/20261023T235010Z/README.md), and
[summary JSON](test/webcam/bmi2/20261023T235010Z/summary.json).

Bulk-reader and lookup-layout follow-up
--------------------------------------

Seven isolated variants tested word-based refill, compact lookup entries,
64-byte lookup alignment, their combinations, and scalar versus SSE2 byte
detection. All seven passed 333 regression tests, pixel comparisons for all
120 camera frames, persistent-decoder checks in five output modes, and source
chunk tests ending at protected memory pages.

The initial reader checked its load bound on every refill and regressed in the
entropy benchmark. The refined version keeps the existing conservative
per-MCU byte budget, requires eight additional buffered bytes at dispatch, and
then performs a bounded-by-budget eight-byte load, scalar FF detection,
byte swap, and six-byte append. FF/stuffing/marker cases use the original byte
reader. Other architectures retain the existing implementation.

Single embedded-frame CPU timings, from a comparison with five bracketed rounds:

| Variant | Median BGR ms/frame | Median entropy/store ms/frame |
|---|---:|---:|
| Contemporary baseline | 6.0697 | 3.1732 |
| Refined scalar bulk reader | 6.0025 | 3.1252 |
| Same design with SSE2 FF detection | 6.1140 | 3.1854 |

The scalar reader saved 1.11% and 1.51% respectively. Full 120-frame sequence
replay confirmed a larger gain in that different workload:

| Build | Mean ms/frame |
|---|---:|
| Contemporary baseline | 6.0900 |
| Refined scalar reader | **5.9398** |

Three rounds each ran baseline, candidate, baseline, with one complete warmup
and three measured passes per process. Candidate reductions were 2.50%, 2.51%,
and 2.39%; the aggregate reduction was **2.47%**, approximately **0.150 ms/frame**.

The layout variants really changed placement: every checked aligned lookup
started at address modulo 64 equal to zero. Compaction halved the lookup from
1,024 to 512 bytes and reduced its containing structure from 1,320 to 808 bytes.
Neither change produced a convincing end-to-end gain in the initial comparison.
Padding other structures is therefore not the next priority on this evidence.

The working decoder remains the baseline; the selected change is saved as
[bulk-once.patch](test/webcam/entropy-opt/bulk-once.patch). See the
[experiment report](test/webcam/entropy-opt/README.md),
[scalar/SSE2 comparison](test/webcam/entropy-opt/20261028T045051Z/README.md),
and [sequence confirmation](test/webcam/entropy-opt/sequence-confirmation/summary.json).
The protected-page checks are not a substitute for malformed-input fuzzing or
an exhaustive input-suspension campaign.

AVX2 32-byte scan-window follow-up
---------------------------------

Implemented 32-byte unaligned AVX2 loads, FF comparisons, and a movemask to
locate a clean prefix reusable across up to five six-byte reservoir refills.
Tested both per-MCU cache lifetime and retention across consecutive fast MCU
calls, with invalidation on slow-path transitions. The fast path requires
32 additional buffered bytes for lookahead.

Five bracketed rounds on the embedded frame measured:

| Variant | Median BGR ms/frame | Median entropy/store ms/frame |
|---|---:|---:|
| Contemporary baseline | 5.9579 | 3.1187 |
| Scalar bulk reader | 5.8943 | 3.0797 |
| Unmodified decoder compiled with `-mavx2` | 5.9770 | 3.1321 |
| AVX2 32-byte local window | 6.0773 | 3.2497 |
| AVX2 32-byte persistent window | 6.1206 | 3.2749 |

The local scanner is 2.00% slower for BGR and 4.20% slower for entropy. The
persistent scanner is 2.73% and 5.01% slower. Both regress in all five paired
BGR comparisons. The compiler-only control is close to baseline, so code
generation alone does not account for most of the regression.

All three new builds pass 333 tests and all camera pixel comparisons. Extended
protected-page checks cover 21 chunk sizes across eight JPEGs, including
sequential/progressive/restart cases, with normal-decode hash references.
Disassembly confirms actual YMM byte comparisons and vector movemasks.
See the [report and patches](test/webcam/avx2-reader/README.md) and
[results](test/webcam/avx2-reader/20261028T053428Z/README.md).
These CPU-specific prototypes compile only `jdhuff.c` with `-mavx2`; runtime
dispatch was not added. The scalar reader remains the selected reader.

Remaining candidates
--------------------

The refill experiments were motivated by the input distribution. Across all camera
frames, the entropy payload contains 44,079,733 bytes and 142,340 stuffed `FF`
bytes (0.3229%). The fraction of non-overlapping input chunks containing no `FF`
is **97.45% for 8 bytes, 95.01% for 16 bytes, and 90.48% for 32 bytes**.

A different SIMD scanner could identify a longer safe region for several
reservoir loads. The tested eight-byte SSE2 detector and amortized 32-byte AVX2
scanners did not help. A different 16-byte scanner or reservoir integration
remains untested.
A separate preprocessing pass or copying the full stream may consume savings.
Other untested candidates are an MSB-aligned reservoir and decoding multiple
MCUs per call while retaining the bit state and DC predictors in registers.

Explicit BEXTR/BZHI extraction, different reservoir layouts, and TZCNT/BSF for
locating exceptions remain untested. Enabling compiler-generated BMI does not
establish the outcome of these algorithm changes. PEXT is a poor first choice
on this Zen 2 CPU: its register form has measured throughput around 19 cycles
per instruction ([uops.info measurements](https://uops.info/html-instr/PEXT_R64_R64_R64.html)).

This checkout has SIMD Huffman encoding, while the measured baseline Huffman
decoder is scalar. Multiple independent frames could provide SIMD lanes, but
divergent symbol counts and output stores add complexity. Batching four frames
at 30 fps makes the oldest wait approximately 100 ms for the batch. Independent
restart segments could provide work within a frame, but this camera emits no
restart interval. Direct planar YUV output is another consumer-dependent option
that has not been benchmarked on the camera sequence.

The 120-frame sequence experiments did not combine fast upsampling with fast
IDCT, or the combined AC lookup with BMI flags; their gains must not be added.
The embedded-frame suite described below includes a combined fast-upsample/
fast-IDCT case, with a different single-frame workload.

Early synthetic measurements
----------------------------

Before capture, a tiled repository image was encoded as a 1920 x 1080,
quality-85, 4:2:0 JPEG. It took approximately 7.9 ms/frame to produce BGR.
Enlarging ordinary Huffman lookahead from eight to ten bits saved approximately
3.2% there, but provided no benefit on the real camera sequence. Restart markers
selected the general MCU decoder but caused only about a 1% total-time increase
in that sample. Optimized Huffman tables reduced file size by approximately
1.6% without improving decode time. These results are illustrative and do not
replace the captured-sequence comparisons above.

Code and reproduction
---------------------

An optional [Google Benchmark suite](benchmarks/README.md) now provides 32
full-frame and stage benchmarks. It embeds a copy of camera frame 60 in the
executable at build time, with no runtime frame loading. Cases cover both APIs,
decoder reuse, output formats/scales, entropy, IDCT, table construction, planar
YUV, and color conversion. Its startup checks verify stage outputs against
complete library decodes. This is a single hot-frame workload, distinct from
the sequence replay above.

```sh
cmake -S . -B /tmp/mjpeg-google-bench -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_SHARED=OFF -DWITH_BENCHMARKS=ON
cmake --build /tmp/mjpeg-google-bench --target mjpeg-bench -j 8
/tmp/mjpeg-google-bench/benchmarks/mjpeg-bench --benchmark_list_tests
```

Google Benchmark v1.10.0 is fetched with a pinned checksum only when this option
is enabled. Benchmark-disabled builds remain C-only. The integrated build
passed 333 tests, including a smoke test that runs every new benchmark case.
A standalone executable was traced and opened no JPEG files at runtime.

The repository's decoder sources are unmodified; experiments are retained as
patches under `test/webcam/`. At the time of writing, the capture and experiment
artifacts are untracked. No commits or deployments were made.

Relevant decoder code: [MCU processing](src/jdcoefct.c),
[Huffman decoder](src/jdhuff.c), [bit extraction macros](src/jdhuff.h),
[IDCT setup](src/jddctmgr.c), [module selection](src/jdmaster.c), and
[per-image memory cleanup](src/jcomapi.c).

The shared [C benchmark](test/webcam/benchmark.c) and
[persistent-decoder verifier](test/webcam/verify.c) are used by these runners:

```sh
python3 test/webcam/benchmark.py test/webcam/20261023T230418Z
python3 test/webcam/fused-ac/run.py test/webcam/20261023T230418Z
python3 test/webcam/bmi2/run.py test/webcam/20261023T230418Z
```

Runners expect their matching prebuilt libraries and headers in `/tmp` and, in
some cases, temporary JPEG fixtures from this session. See each experiment's
notes before rerunning. Temporary builds include `/tmp/mjpeg-release`,
`/tmp/mjpeg-profile`, `/tmp/mjpeg-lookahead10`, `/tmp/mjpeg-fused10` through
`/tmp/mjpeg-fused12`, and `/tmp/mjpeg-bmi2`; these may need reconstruction in
a later session. Saved patches, commands, disassembly, JSON, per-frame CSVs,
test logs, and comparison binaries provide the durable experiment record.

Hardware verification after enabling perf: five alternating paired trials,
100 frames each, decode-only collection without multiplexing. Scalar bulk
reduces median entropy cycles 2.95%, instructions 5.40%, and branches 7.57%;
full BGR cycles fall 3.02%. Hardware branch misses rise slightly (0.78% entropy),
and entropy cache misses vary substantially between pairs. This verifies a
cycle benefit but does not support a reliable entropy cache-miss reduction.
Raw counters and a FIFO-gated perf runner accompany the cache investigation.

The [scalar cache investigation](test/webcam/cache-profile/README.md) adds
Callgrind simulation and native cache-disturbance experiments. Entropy scalar
bulk reduces instructions 5.39%, data references 5.98%, and branches 7.87%, while
simulated L1 data misses remain exactly 5,810/frame for both readers. This
supports reduced execution work rather than reduced cache misses as the likely
benefit; simulated events cannot establish actual stall cycles. Raw profiles,
an embedded-frame driver, and a reproduction runner are retained there.

Before the hardware verification above, performance counters were unavailable
(`perf_event_paranoid=4`), so
branch/cache bottleneck explanations remain hypotheses rather than direct
counter measurements. CPU frequency was not fixed. The repeated timings and
same-run baselines support the modest conclusions above, not a guaranteed
speedup across other workloads.
