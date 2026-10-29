# Multi-symbol AC Huffman LUT experiment

Ryzen 9 3900X, GCC 13.3, 2026-10-28. Embedded 371,718-byte webcam fixture,
1920x1080 baseline YCbCr 4:2:2. Experiments are isolated in `/tmp`; production
decoder sources remain unchanged. Patches here apply to the original checkout
and include the scalar bulk reader and permanent-pool lookup cache support.

## Implementation

Build a LUT indexed by the next 8 or 10 bits. Each eight-byte entry holds:

- Two signed coefficient values, already extended from JPEG amplitude bits.
- Total bits consumed.
- Two coefficient advances (zero run plus one).
- Number of decoded nonzero coefficients, one or two.

A table is 2 KiB at 8 bits, 8 KiB at 10 bits, per AC Huffman table. An entry
decodes two complete symbol/amplitude sequences when both fit, otherwise one
when it fits. No complete first coefficient means fallback. EOB, ZRL, long
codes/values, discarded coefficients, and slow input paths retain the original
decoder. Before accepting a hit, check that its coefficient advances stay in
the current 8x8 block. Neither a pair nor its amplitude crosses a block boundary.

Tables are generated from the JPEG's actual Huffman definitions, not hardcoded
webcam codes. A permanent-pool cache survives finish/abort; compare all DHT code
counts and symbol bytes before reuse. Build/rebuild cost occurs during scan
setup. Timings below use a persistent decompressor and unchanged frame tables;
they do not measure first-frame table construction cost.

The first version branches on whether an entry represents one or two values.
The follow-up always makes two stores: one-symbol entries use `step2=0` and
`value2=value1`, repeating the first store. This removes the count-dependent
branch without writing a different coefficient for single-symbol hits.
The `single10` control has the same entry format, width, cache lifetime and
single-symbol/value fusion but never builds pairs.

## Branchless pair results

Five trials in a separate comparison pass, with freshly measured controls:

| Variant | Entropy ms | Full BGR ms | Entropy cycles | Entropy instructions | Entropy branch misses |
|---|---:|---:|---:|---:|---:|
| Original | 3.2090 | 6.1170 | 13.766M | 33.988M | 171,418 |
| Scalar bulk | 3.1137 | 5.9419 | 13.374M | 32.153M | 174,089 |
| Branchless pair, 8 bits | 3.1018 | 5.9604 | 13.328M | 23.144M | 232,989 |
| Branchless pair, 10 bits | **2.5927** | **5.4812** | **11.114M** | **21.250M** | **174,329** |
| Single, 10 bits | 2.9217 | 5.8803 | 12.557M | 25.178M | 183,168 |

The 10-bit branchless pair table reduces entropy time **16.73%** and cycles
**16.90%** versus scalar bulk, and full BGR time **7.75%** / cycles **8.24%**.
Versus the original decoder, native entropy time falls **19.21%**, full BGR
**10.39%**. Pair decoding also beats the same-pass single-symbol control:
entropy cycles **11.49%** lower, full BGR cycles **7.35%** lower. The control
retains its original conditional-store implementation, so that comparison is
between these complete variants rather than an isolated estimate of pairing.

Entropy instructions fall **33.91%** and branches **24.06%** versus scalar;
branch misses are essentially unchanged (+0.14%). Every paired entropy cycle
trial improves (15.75–18.29%). Four of five paired full-cycle trials improve;
one is 0.34% worse. This is a successful prototype on this CPU and fixture,
not yet evidence for every JPEG workload. The 8-bit table is approximately
break-even despite many fewer instructions.

### Actual pair coverage

Separate untimed instrumentation (`coverage.json`) counts two entropy frames,
including warmup. At 10 bits: 733,656 AC fast-loop attempts, 576,086 LUT hits,
268,772 of them pairs. Thus 78.52% of attempts hit the fused LUT and 46.65% of
hits produce two coefficients. There are 1,002,428 decoded AC symbols in those
fast loops (attempts plus extra pair symbols); **53.62% of symbols belong to
pairs**. The 8-bit version has only 174,290 pairs for the same logical symbol
count. These include neither DC nor the final slow-path tail of the image.

## Initial conditional-store results

Five trials, median of per-trial native frame medians; hardware values are
median counts/frame from separate five-trial PMU runs:

| Variant | Entropy ms | Full BGR ms | Entropy cycles | Entropy instructions | Entropy branch misses |
|---|---:|---:|---:|---:|---:|
| Original | 3.1868 | 6.0599 | 13.771M | 33.988M | 172,819 |
| Scalar bulk | 3.0954 | 5.9192 | 13.351M | 32.153M | 174,548 |
| Pair, 8 bits | 3.7944 | 6.6743 | 16.358M | 24.478M | 343,633 |
| Pair, 10 bits | 3.2195 | 6.0546 | 13.892M | 21.684M | 305,080 |
| Single, 10 bits | 2.9173 | 5.8194 | 12.543M | 25.178M | 183,329 |

Pairs remove instructions but lose on cycles. Branch misses increase sharply;
this motivated the follow-up that removes the count-dependent store branch.
The counters alone do not assign misses to individual instructions.

## Validation and measurement

All three initial LUT variants and both branchless variants pass 332 CTest
checks each. Each also matches decoded pixels for all 120 webcam frames, a
persistent decoder across five modes and mixed baseline/progressive images,
and protected-page input chunks at ten boundary sizes for five images.
The single10 control is reused unchanged in the branchless comparison.

Both benchmark passes use CPU 0, five trials, 100 measured frames and five
warmups per run. Rotate/reverse the five-variant order between trials. Native
timing runs without perf. Hardware runs use FIFO-gated perf collection around
each decode; setup/warmup/entropy abort are excluded. Collect cycles,
instructions, branches and branch misses together, with 100% running time and
no multiplexing. Do not use hardware-run wall times as native decode times:
those include control-channel waits. All native/hardware full output hashes
match. Entropy driver hashes only its final MCU; full-frame equality is checked
separately. CPU frequency is not fixed; prefer within-pass paired comparisons.

`results.json`, `summary.json`, `*.perf.csv`, and `*-ctest.log` preserve the
initial results. Follow-up results are under `branchless/`, with test progress
and summary in `run-branchless.log`.

## Full-sequence confirmation

Replay all 120 preloaded frames, full BGR, three measured sequence passes after
one full warmup pass, in three rounds with rotating variant order. Mean across
the equally sized rounds:

| Variant | Mean ms/frame |
|---|---:|
| Original | 6.0670 |
| Scalar bulk | 6.0168 |
| Branchless pair, 10 bits | **5.4501** |

This is **9.42% less time than scalar bulk**, **10.17% less than original**.
The pair variant improves over scalar in every round (11.46%, 9.23%, 7.52%).
The scalar-versus-original gap varies from earlier experiments, reinforcing
the need for contemporary controls and showing native clock/load variation.
These sequence results have no hardware profiling overhead. `sequence.py`
reproduces this test; raw frame CSVs and summary are in `sequence/`.

## Reproduction

From the repository root, `python3 test/webcam/multisymbol_prepare.py` creates
`/tmp/mjpeg-multisymbol-src` and the initial patch. It requires the retained
scalar and fused-AC patches. The script refuses to overwrite an existing tree.
Configure release static builds in `/tmp/mjpeg-multi8`, `/tmp/mjpeg-multi10`,
and `/tmp/mjpeg-single10`, using respectively:

```text
-DCMAKE_C_FLAGS=-DMJPEG_FUSED_BITS=8
-DCMAKE_C_FLAGS=-DMJPEG_FUSED_BITS=10
"-DCMAKE_C_FLAGS=-DMJPEG_FUSED_BITS=10 -DMJPEG_PAIR=0"
```

Use `-DCMAKE_BUILD_TYPE=Release -DENABLE_SHARED=OFF -DBUILD=20261024`, then
`cmake --build <build> -j 6`. Run `python3 test/webcam/multisymbol/run.py`.
It also needs the earlier original/scalar builds and embedded fixture object
in `/tmp`; their paths are explicit in the script.

`python3 test/webcam/multisymbol/prepare_branchless.py` creates the second source
tree and its self-contained patch. Build 8/10-bit variants in
`/tmp/mjpeg-multi8-branchless` and `/tmp/mjpeg-multi10-branchless`, then run
`python3 test/webcam/multisymbol/run.py --branchless`.

`coverage.py` builds separate, untimed instrumented archive copies to count
actual LUT hits on the fixture. It does not alter timed libraries. Its counts
cover fast-path AC iterations only and include one warmup and one measured
frame. Neither diagnostic timings nor static table occupancy represent native
decoder performance.
