# Scalar bulk reader: cache investigation

## Hardware verification (2026-10-28)

After the user enabled `kernel.perf_event_paranoid=2`, ran
`python3 test/webcam/cache-profile/hardware.py`. Five alternating paired trials,
100 measured frames each, five warmup frames, CPU 0. Perf starts disabled
(`-D -1`); the driver uses an acknowledged perf control FIFO to enable/disable
events around each decode. Setup/warmup/entropy abort are excluded. Counter
groups run separately; all events have 100% running time, no multiplexing.
The FIFO handshake introduces small collection-boundary overhead, so use the
earlier native experiment for uninstrumented wall time. Timings printed during
hardware profiling include handshake waits and should not be compared as pure
decode latency. An attempted `prctl` gating method produced no counts with
these perf-owned events and was replaced with the supported control FIFO.

Median hardware counts per frame:

| Event | Entropy original / scalar | Change | Full BGR change |
|---|---:|---:|---:|
| Cycles | 13,751,305 / 13,345,566 | -2.95% | -3.02% |
| Instructions | 33,987,693 / 32,153,153 | -5.40% | -2.85% |
| Branches | 3,920,161 / 3,623,342 | -7.57% | -5.67% |
| Branch misses | 171,893 / 173,238 | +0.78% | +0.70% |
| L1 data loads | 4,368,627 / 4,066,695 | -6.91% | -1.93% |
| L1 data load misses | 732 / 861 | +17.60% | -2.18% |

Entropy cycles decreased in every pair (2.85–3.31%); full cycles decreased
2.12–5.82%. Output hashes match. Hardware branch misses **increase slightly**,
contrary to the simulated predictor's decrease: fewer branches does not mean
fewer branch mispredictions. Entropy L1 misses are small and noisy: paired
changes span -27.57% to +40.70%. Generic `cache-misses` also varies in direction
between pairs; its median changes (-4.06% entropy, -4.59% full) are insufficient
evidence for a reliable cache benefit. These generic cache events must not be
equated with the simulated L2 events. Hardware prefetch and actual event
definitions also prevent direct equality with simulated miss counts.

The hardware result supports reduced instruction/branch execution as the main
opportunity; it does not establish the exact stall-cycle cause. Counters are
aggregate events, without address or pipeline-stall attribution. Raw CSVs and
all 40 runs are in `hardware-results/`. `hardware.py` requires rebuilt drivers
with the optional `MJPEG_PERF_CONTROL` FIFO support in `driver.cc`.

Measured 2026-10-28 on Ryzen 9 3900X, GCC 13.3. Compared original decoder
against `../entropy-opt/bulk-once.patch`; decoder sources in the working tree
remain unchanged. Embedded 1920x1080 4:2:2 fixture from `benchmarks/data`.

## Findings

The scalar improvement is consistent with less instruction/branch work, not
fewer cache misses. Callgrind entropy-only counts per frame, after warmup:

| Event | Original | Scalar bulk | Change |
|---|---:|---:|---:|
| Instructions | 34,019,040 | 32,184,500 | -5.39% |
| Data references (reads + writes) | 4,074,938 | 3,831,435 | -5.98% |
| Branches (conditional + indirect) | 3,773,882 | 3,477,063 | -7.87% |
| Simulated branch mispredictions | 189,599 | 186,509 | -1.63% |
| Simulated L1 data misses | 5,810 | 5,810 | same |
| Simulated L2 data misses | 95 | 99 | negligible difference |
| Simulated L1 instruction misses | 37 | 43 | negligible difference |

The 371,718-byte JPEG occupies 5,809 cache lines before allowing for its
starting alignment. Approximately one pass through compressed input explains
most entropy L1 misses; these counts alone do not identify every missed address.
With a competing 2 MiB buffer touched before every decode, simulated entropy
L2 data misses increase to 5,914 original / 5,913 scalar per frame, while L1
data misses remain similar (5,922 / 5,921). Full decoding has 251,568 / 251,554
L1 data misses and exactly equal 103,300 L2 data misses in the warm case.
Its output and other stages dominate these cache events.

`decode_mcu` accounts for about 97% of collected entropy instructions. Its
machine code grows from 6,055 to 6,357 bytes with scalar bulk; the simulated
instruction misses give no evidence that this modest growth is problematic.
The identical input traversal and previously unsuccessful table-alignment
experiment make table packing/alignment a lower priority than reducing refill
and Huffman dependency/branch work. Fewer data references do not imply fewer
cache-line fetches: most removed references were already hitting cache.

## Native sensitivity experiment

Median of three trial medians, each trial 30 measured frames after three warmup
frames, CPU 0, alternating variant order. Touch one byte per 64-byte line in a
competing buffer immediately before decoding; disturbance is outside the timer.

| Competing buffer | Entropy original / scalar ms | Full BGR original / scalar ms |
|---|---:|---:|
| None | 3.1233 / 3.0917 | 5.9612 / 5.8505 |
| 32 KiB | 3.1402 / 3.1222 | 5.9298 / 5.8494 |
| 2 MiB | 3.1377 / 3.1266 | 5.9387 / 5.8671 |
| 32 MiB | 3.1463 / 3.1272 | 6.0277 / 5.9571 |

These perturbations have modest effects on this repeatedly decoded frame.
They are competing-data experiments, not guaranteed cache flushes or precise
cache latency measurements. CPU frequency was not fixed; timing differences
this small should not be generalized to every stream or CPU. Full-frame output
hashes match across variants and conditions; entropy hashes check the final MCU
only (the earlier sequence verifier checks full output).

## Method and limitations

Hardware `perf` counters are denied (`perf_event_paranoid=4`). All cache,
instruction, and branch counts above come from Valgrind 3.22 Callgrind simulation,
not PMU measurements. Configured I1 and D1: 32 KiB, 8-way, 64-byte lines;
LL: 512 KiB, 8-way, 64-byte lines, representing this CPU's **L2**. The simplified
model omits the real L3 and hardware prefetch behavior; its branch predictor is
not Zen 2's. Miss counts cannot establish stall cycles or bandwidth saturation.

Each simulation collects three frames after two warmup frames. Instrumentation
is enabled throughout warmup/setup/disturbance, but collection is enabled only
inside the measured decode region. Entropy setup and abort are excluded; full
decode includes header/start/scanlines/finish. Coefficient storage is reused
per MCU in the entropy harness, unlike the full output pipeline. Never use
Valgrind elapsed times as native benchmark results.

Raw data: `results/native.json`, `results/simulated.json`, individual Callgrind
files/logs, and earlier function annotations in `pilot/`.

## Reproduction

Build `driver.cc` twice, substituting each build's include/library paths:

```sh
c++ -O3 -g -std=c++17 -Wall -Wextra \
  -I/tmp/mjpeg-google-bench -Isrc -Ibenchmarks \
  test/webcam/cache-profile/driver.cc \
  /tmp/mjpeg-google-bench/benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o \
  /tmp/mjpeg-google-bench/libjpeg.a -lm \
  -o test/webcam/cache-profile/driver-baseline
```

For scalar use `/tmp/mjpeg-entropy-opt-build/bulk-once` and
`/tmp/mjpeg-entropy-opt-src/bulk-once/src`, output `driver-scalar`.
Requires Valgrind headers and the previously configured embedded fixture build.
Then run `python3 test/webcam/cache-profile/run.py`. The runner pins native
measurements to CPU 0 and finishes them before starting simulations.

Next useful evidence would be real cycles, branch misses and L1/L2/LLC events
when PMU access is available, followed by assembly work on refill branches and
the serial Huffman lookup/bit-reservoir dependency chain. These measurements
do not justify a cache-layout change by themselves.
