# zenjpeg-inspired bit-reader and DC-dispatch experiments

Measured 2026-10-31, Ryzen 9 3900X, GCC 13.3 release, CPU 0. Embedded 1920x1080
4:2:2 webcam JPEG (16,200 MCUs). Source review and upstream revision are in
`extra/zenjpeg-review.md`. These independently written C experiments keep our
two-symbol LUT and test individual implementation choices. They are not a
benchmark of the complete Rust zenjpeg decoder.

**Result: no convincing full-NV12 improvement. Keep threshold-pair10.**

## Controls and variants

All start from the previous winner: scalar six-byte bulk refill, branchless
10-bit two-AC-symbol table, persistent lookup caching, and pre-shifted long-code
thresholds. Production codec sources are unchanged.

- **Control:** `/tmp/mjpeg-stb-build/threshold-pair10`.
- **Defer-drop:** postpone consuming the short Huffman lookup's bits until its
  length is known. This is a control for the scheduling change needed by an
  MSB-aligned reservoir: the original right-aligned macro can speculatively
  subtract a length and restore only the count, whereas shifting an MSB
  reservoir would discard bits. Keep the original reservoir representation.
- **Left64:** same deferred-consumption macro, but maintain an MSB-aligned
  64-bit reservoir inside the fast MCU decoder. Fixed-width lookups use constant
  shifts; consumption shifts the reservoir. Keep the original fixed six-byte
  refill and input budget. Convert to/from the original representation once
  per MCU; permanent state and the slow/suspending path remain right-aligned.
  This conversion overhead is part of the measured implementation, so the
  result does not rule out every fully MSB-native decoder architecture.
- **Variable-refill:** retain right alignment and the original <=16-bit refill
  trigger, but consume as many clean bytes as fit: **6–8**, not zenjpeg's full
  5–8-byte policy. This isolates refill size from alignment/trigger changes.
  Handle the eight-byte/64-bit case explicitly, avoiding a shift by 64.
- **Prefix4:** after the eight-byte FF check fails, check the first four bytes;
  append them together if clean, otherwise retain bytewise marker/stuffing
  handling. This keeps the fixed-size bulk policy otherwise unchanged.
- **DC-dispatch:** track whether AC coefficients were stored while decoding
  each block, publish a per-MCU DC-only mask, and bypass the normal IDCT for
  eligible constant blocks. This first version updates a mask in coefficient
  paths and therefore adds hot-loop work.
- **DC-lite:** a separately confirmed refinement. Infer a conservative DC-only
  flag from `k==1` at block completion, avoiding per-coefficient mask updates.
  This recognizes an immediate EOB; a valid zero block encoded with leading
  ZRLs uses the original IDCT instead. The conservative flag misses that
  shortcut opportunity without changing the reconstructed samples.

The DC shortcuts apply only to baseline Huffman, accurate ISLOW, 8-bit 8x8
output with dequantized DC in [-4096,4095]. That bound preserves intermediate
semantics for the constant-fill shortcut; other values/methods/scales use the
original kernel. Slow-path fallback invalidates the side-channel mask. The
metadata fields belong to each decoder instance. Fast-IDCT runs retain the
tracking overhead but use the original IDCT, exposing the cost of a feature
that cannot help that method.

## Main comparison

Five rotated/reversed rounds, 100 measured frames after five warmups, native
runs first and then gated hardware runs. Event group: user cycles,
instructions, branches, branch misses, 100% running time without multiplexing.
Counter collection covers only decode; setup/warmup are excluded. Native time
is the median of five per-trial frame medians; hardware is the median count per
frame across five trials. Hardware wall times include FIFO waits and are not
used as native timings. Full output is raw-strip NV12 with AVX2 packing.

| Variant | Accurate NV12 ms | Fast NV12 ms | Accurate cycle change | Fast cycle change |
|---|---:|---:|---:|---:|
| Threshold-pair10 control | 4.4267 | 4.0122 | baseline | baseline |
| Defer-drop control | 4.4208 | 3.9971 | +0.66% | +0.04% |
| Left64 | 4.4901 | 4.0425 | +1.78% | +0.84% |
| Variable-refill | 4.5148 | 4.0866 | +1.69% | +2.90% |
| Prefix4 | 4.4204 | 4.0250 | +0.20% | +0.59% |
| DC-dispatch | 4.4482 | 4.1750 | +1.35% | +4.13% |

Positive cycle change means slower. Small native-time improvements are not
confirmed by the counters. CPU frequency was not fixed; compare within these
runs, not against absolute timings from other sessions.

| Variant | Entropy cycles/frame | Entropy instructions/frame |
|---|---:|---:|
| Control | 11.006M | 20.958M |
| Defer-drop | 10.994M | 20.958M |
| Left64 | 10.908M | 22.206M |
| Variable-refill | 11.214M | 21.292M |
| Prefix4 | 11.098M | 20.582M |
| DC-dispatch | 11.075M | 22.428M |

Left64 reduces isolated entropy cycles 0.88% versus the main control (0.78%
versus defer-drop), yet loses on complete NV12. It also executes 1.248M more
entropy instructions. Its small helper is inlined; no `left_get_bits` function
remains in the compiled object. Prefix4 executes fewer instructions but more
cycles. These are aggregate observations, not proof of a particular pipeline
stall/cache cause. Benchmark the complete output path before selecting changes.

## Cheaper DC-only flag confirmation

Same method, separate contemporaneous control, five native and five PMU rounds:

| Measurement | Control | DC-lite | Change |
|---|---:|---:|---:|
| Accurate NV12 native ms | 4.4493 | 4.4581 | +0.20% |
| Accurate NV12 cycles | 19.179M | 19.088M | -0.47% |
| Fast NV12 native ms | 4.0771 | 4.1263 | +1.21% |
| Fast NV12 cycles | 17.158M | 17.365M | +1.21% |
| Entropy cycles | 10.986M | 11.306M | +2.92% |

Accurate timings vary in direction between pairs; three of five hardware pairs
improve and two regress, while native medians do not show a gain. Fast-IDCT and
entropy regress in every pair. This is not sufficient to promote the flag.
Libjpeg already has SIMD coefficient-zero shortcuts; bypassing them must save
more than the tracking, dispatch and constant-fill overhead. A fully integrated
metadata scheme could behave differently, but this experiment establishes no
reliable end-to-end benefit.

## Correctness and artifacts

Every one of the six variants passed **332 CTest tests**, exact decoded pixels
for **all 120 captured frames**, persistent decoder reuse in five modes with
mixed baseline/progressive inputs, and protected-page source chunks (five
images, ten sizes). Hashes cover complete NV12 output and agree across all
variants in each IDCT mode. Entropy-only hashes cover only the final MCU and
are supplemental to full-image validation. Header/state representation changes
were confined to isolated source trees.

Main records: `summary.json`, `results.json`, `validation.json`.
Refined DC records: `confirmation-dc-lite/summary.json`, `results.json`,
`validation.json`. Per-run CSVs, binaries and detailed logs remain local.
The standalone drivers include the previously validated NV12 implementation;
they are not a public codec API. No GPU upload/encoder work is measured.

## Reproduce

Requires the retained threshold-pair10 source/build and earlier embedded
fixture/Google Benchmark objects under `/tmp`, as listed in the scripts:

```sh
python3 test/webcam/zenjpeg-ideas/prepare.py
python3 test/webcam/zenjpeg-ideas/build.py
python3 test/webcam/zenjpeg-ideas/run.py
```

To run only the refinement against the control:

```sh
python3 test/webcam/zenjpeg-ideas/build.py --only dc-lite
python3 test/webcam/zenjpeg-ideas/run.py --only dc-lite
```

Preparation refuses existing directories by default. `--refresh --only NAME`
regenerates the known variant files from the retained control without replacing
other source-tree files. Each saved patch is self-contained against the original
codec and includes earlier successful optimizations; apply alternatives
individually, not as a series. No combinations of the losing refill/alignment
variants were promoted, and the complete Rust decoder was not benchmarked.
