# Larger assembly blocks in the entropy decoder

2026-10-31, Ryzen 9 3900X, GCC 13.3 and Clang 18.1.3, `-O3 -DNDEBUG`;
`-mbmi2` only on jdhuff.c. Production codec sources are unchanged.

## Direct comparison of the best retained GCC and Clang builds

GCC ordinary C/BMI2 versus Clang receive assembly/BMI2, run in the same cohort:

| NV12 mode | GCC best | Clang best | Clang time overhead |
|---|---:|---:|---:|
| Accurate IDCT | 4.3412 ms | 4.4231 ms | +1.89% |
| Fast IDCT | 3.9233 ms | 4.0800 ms | +4.00% |

Four brackets per mode, alternating GCC-Clang-GCC and Clang-GCC-Clang.
Each process preloads all 120 frames, warms up with a complete pass, then
times three full passes. CPU 0; loading, allocation and hashing excluded.
GCC wins all eight brackets. Accurate per-bracket Clang overhead ranges
0.98–2.71%; fast ranges 3.07–5.02%. Output hashes agree in every bracket.
Both binaries use the same benchmark driver and NV12 packing implementation.
Their codec libraries are built with their respective compilers; the Clang
decoder also includes the receive assembly source change described below.

Records: `best-sequence-summary.json`. Reproduce with:

```sh
python3 test/webcam/bmi-intrinsics/assembly/sequence.py --best
```

Two variants were built for each compiler:

* **receive:** combine bit-count update, SHRX, BZHI, threshold construction,
  and JPEG amplitude sign extension into one inline assembly block. It uses
  CMP/SBB to form the negative-amplitude adjustment without a branch.
* **pair:** include the receive change, and replace the fused AC hit path with
  one assembly block: 10-bit lookup, validity/bounds checks, bit consumption,
  zigzag mapping, and two coefficient stores. A miss returns to the existing
  Huffman fallback without changing the output, bit count, or position.

These changes affect the **fast MCU decoder only**. Slow decoding, refill,
marker handling, table construction and error handling remain C. The pair
kernel is specific to the existing 10-bit, 8-byte entry format; compile-time
checks protect entry size/field offsets and coefficient/order element sizes.

## Results against each compiler's ordinary C control

| Variant | Entropy time | Entropy cycles | Accurate NV12 time | Fast NV12 time |
|---|---:|---:|---:|---:|
| GCC receive | +1.57% | +0.34% | +0.60% | +0.36% |
| GCC receive + pair | +3.79% | +4.13% | +0.04% | +1.57% |
| Clang receive | -0.35% | -0.56% | -2.19% | -1.93% |
| Clang receive + pair | +4.67% | +4.54% | +2.16% | +2.36% |

Positive means slower. Five rotated/reversed 100-frame native rounds followed
by five gated, non-multiplexed PMU rounds, CPU 0, embedded webcam frame. CPU
frequency was not fixed. The GCC/Clang controls in this cohort have entropy
times of 2.5333/2.6004 ms, accurate NV12 4.4546/4.5802 ms, and fast NV12
4.0286/4.2471 ms. Each assembly candidate's archives differ from its compiler's
control only in jdhuff.c.o; both libjpeg and TurboJPEG are checked.

### Full capture confirmation for Clang receive

120 preloaded frames, three measured passes after a full warmup pass, three
control-candidate-control brackets per IDCT method, CPU 0. Loading and hashing
are outside the decode timers. Output hashes match over the whole capture.

| Mode | Bracketed Clang control | Clang receive | Time change |
|---|---:|---:|---:|
| Accurate NV12 | 4.5528 ms | 4.4570 ms | -2.10% |
| Fast NV12 | 4.1887 ms | 4.0792 ms | -2.61% |

All three accurate brackets improve (2.11%, 2.08%, 2.13%); all three fast
brackets improve (3.62%, 1.94%, 2.27%). This supports keeping receive as a
Clang candidate on this CPU. It does not establish an improvement under GCC
or that Clang now beats GCC: the full sequence confirmation brackets only
Clang against Clang. These results do not isolate exactly why the smaller
entropy gain becomes a larger full-pipeline gain; surrounding code generation
and interaction with reconstruction remain factors.

## What the assembly comparison shows

Both kernels are inlined under both compilers: no extra helper calls in the
hot path. Explicit early-clobber outputs protect input registers; flag
clobbers are declared; the pair block also declares its memory effects.

The larger pair block increases retired branches by approximately 710k/frame
under GCC and 594k/frame under Clang compared with each ordinary C control.
Its internal branch targets plus returning hit/miss to surrounding C introduce
additional control flow. Rewriting the arithmetic alone does not control the
whole loop's register allocation or branch structure. The next experiment
would own that boundary, for example an `asm goto` fast path or a complete AC
loop with explicit refill/fallback exits. Neither has been implemented here.

The receive block is about a dozen instructions; the pair block is about
thirty, including branches. The complete entropy loop is still C.

## Validation and artifacts

All four decoder variants passed 332 CTest tests each, exact pixels on all
120 captured frames, persistent decoding in five modes with mixed images,
and guarded reads on five images with ten chunk sizes. NV12 and entropy hashes
match the controls.

The exact private kernels also passed 131,070 amplitude cases (widths 1..16,
varying reservoir positions) and 64,512 synthetic fused-entry hit/miss cases
(all 1024 prefixes at all 63 AC positions). Tests check state changes and
surrounding coefficient storage. GCC and Clang pass both AT&T and Intel
assembly dialects.

* `kernels.h`: readable assembly helpers.
* `gcc-receive.patch` / `clang-receive.patch`: receive source deltas.
* `gcc-pair.patch` / `clang-pair.patch`: receive + pair deltas.
* Patches apply to the threshold-pair10 source, not the untouched codec.
* `*.asm` / `*.diff`: measured-object disassembly and comparisons.
* `isolation.json`: archive isolation; `summary.json` / `results.json`: timing
  and PMU data; `sequence-summary.json`: full-capture confirmation.

Runtime BMI2 dispatch would be required for portable integration. No candidate
was installed into the production codec or committed.

## Reproduce

Requires existing GCC/Clang controls and benchmark artifacts documented in
the parent experiments. Build preparation refuses existing candidate trees.

```sh
python3 test/webcam/bmi-intrinsics/assembly/build.py
python3 test/webcam/bmi-intrinsics/assembly/check.py
python3 test/webcam/zenjpeg-ideas/run.py --config test/webcam/bmi-intrinsics/assembly/experiment.json
python3 test/webcam/bmi-intrinsics/assembly/sequence.py
```
