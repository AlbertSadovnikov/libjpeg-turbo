# Compiler optimization flags: generic versus Zen 2

2026-10-31, Ryzen 9 3900X, GCC 13.3 and Clang 18.1.3.

**Generic CPU tuning explained much of Clang's earlier deficit.** Plain C
Clang with `-O3 -mtune=znver2` comes within about 0.3% of the existing GCC
winner on the full capture, using the same decoder source. It does not need
the receive assembly patch to become competitive on this host.

## Configuration audit

Both original builds had `-O3 -DNDEBUG`, SIMD enabled, and `-mbmi2` on
jdhuff.c. Clang's effective cc1 command shows `-target-cpu x86-64` and
`-tune-cpu generic`; GCC also defaults to x86-64/generic. There was no
accidental Debug build, disabled SIMD, or missing BMI2 flag.

`-mtune=znver2` changes CPU tuning without enabling additional ISA features;
`-march=znver2` also permits the Zen 2 instruction set. These are distinct
experiments. All new release flags apply to the codec's C files, not just
jdhuff.c. NASM SIMD routines keep their existing implementation. Benchmark
drivers and NV12 packing are compiled identically across variants.

## Embedded-frame matrix

All values are ms/frame, measured in the same cohort:

| Build | Entropy | Accurate NV12 | Fast NV12 |
|---|---:|---:|---:|
| GCC C, O3 generic | 2.5571 | 4.4390 | 4.0336 |
| Clang C, O3 generic | 2.6097 | 4.5903 | 4.2543 |
| Clang receive asm, O3 generic | 2.6043 | 4.4432 | 4.1464 |
| Clang C, O2 generic | 2.6383 | 4.4259 | 4.1255 |
| Clang C, O3 mtune=znver2 | 2.5803 | 4.4031 | 3.9959 |
| Clang receive asm, O3 mtune=znver2 | 2.5662 | 4.5286 | 4.6279 |
| Clang receive asm, O3 march=znver2 | 2.5787 | 4.3552 | 3.9602 |
| GCC C, O3 mtune=znver2 | 2.5219 | 4.4810 | 4.2249 |

Plain Clang CPU tuning improves full NV12 roughly 4% accurate / 6% fast
versus generic Clang C here. Hardware cycles support that result: reductions
are 4.25% / 6.20%. O2 is not a general winner: it improves full NV12 but
regresses entropy. GCC tuning also improves entropy while regressing full
NV12. Combining Clang tuning with the receive block is particularly poor in
fast mode. Flag and source effects are not additive.

Five rotated/reversed 100-frame native rounds, then five gated PMU rounds,
CPU 0. No counter multiplexing. CPU frequency was not fixed. Full-codec
flag changes can alter reconstruction code and code layout as well as the
entropy loop. These counters do not isolate the cause of each interaction.

## Full-capture confirmation against existing GCC winner

Three GCC-candidate-GCC brackets per candidate and IDCT mode, candidate order
rotated; 120 preloaded frames; three measured passes after a full warmup;
CPU 0. Loading, hashing and allocation are outside decode timers.

| Clang candidate | Mode | Bracketed GCC C | Clang | Clang time change |
|---|---|---:|---:|---:|
| C, mtune=znver2 | Accurate | 4.3121 ms | 4.3259 ms | +0.32% |
| C, mtune=znver2 | Fast | 3.9161 ms | 3.9297 ms | +0.35% |
| Receive asm, march=znver2 | Accurate | 4.3196 ms | 4.2837 ms | -0.83% |
| Receive asm, march=znver2 | Fast | 3.9044 ms | 3.8639 ms | -1.04% |

Positive means Clang is slower. CPU-specific Clang wins all three fast
brackets (0.81%, 0.71%, 1.59% reductions); accurate wins two brackets
(0.76%, 1.74%) and loses the third by 0.02%. The difference is small.
The GCC reference is the retained generic-tuned BMI2 build, not a matching
march=znver2 GCC build. Do not claim this ranks fully optimized GCC versus
Clang for all workloads. The march build has a higher ISA requirement than
the generic/tune builds.

All output hashes agree. Each matrix build passes 332 CTest tests, exact
pixels on 120 captured frames, persistent decoding in five modes with mixed
images, and guarded source tests on five images/ten chunk sizes.

## Current implications

For this Zen 2 host, keep ordinary C as a serious Clang candidate and include
`-mtune=znver2` in performance testing. Keep the generic GCC winner as the
GCC reference; its tuned alternative did not improve full NV12. The Clang
march/receive build is a promising machine-specific candidate, rather than
a portable default. Production source/build settings remain unchanged.

PGO, LTO, a matching march GCC build, and newer compiler versions were not
tested here. In particular, neither PGO nor LTO was enabled in the original
comparison. These remain separate experiments, not established explanations
for the remaining small differences.

Reproduce with the retained controls and source trees:

```sh
python3 test/webcam/bmi-intrinsics/compiler-flags/build.py
python3 test/webcam/zenjpeg-ideas/run.py --config test/webcam/bmi-intrinsics/compiler-flags/experiment.json
python3 test/webcam/bmi-intrinsics/compiler-flags/sequence.py
```

Build preparation refuses existing candidate directories. Exact flags are
in `build-flags.json`; timing/counter data in `summary.json` / `results.json`;
full-capture brackets in `sequence-summary.json`. Local object disassemblies
and `disassembly-summary.json` record instruction selection. Static instruction
counts include fast and slow paths and padding, not executed instruction counts.
