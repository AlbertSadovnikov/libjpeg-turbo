# Explicit SHRX/SHLX decoder comparison

2026-10-31, GCC 13.3, Ryzen 9 3900X. The source-only delta is
[`../explicit-shifts.patch`](../explicit-shifts.patch), against threshold-pair10.
The complete reconstruction is `../explicit-shifts-complete.patch`.
Both control and candidate compile jdhuff.c with `-mbmi2`; only that object's
archive member changes, verified for libjpeg and TurboJPEG. Production source
is unchanged.

The patch forces variable right shifts in GET_BITS/PEEK_BITS and variable
left shifts in mask construction and HUFF_EXTEND using GCC inline assembly.
This GCC has no public SHRX/SHLX intrinsics. Constant left shifts remain C
constant expressions. No explicit BZHI is included in this candidate.

Fast MCU static sites: compiler 13 SHRX/6 SHLX; explicit 12 SHRX/6 SHLX.
Source-mapped debug text matches measured release text byte-for-byte, as
recorded in `audit/summary.json`. Explicit wrappers do not preserve the
compiler's scheduling, reuse, or loop-layout decisions simply because the
same opcodes are involved.

| Mode | Compiler ms/frame | Explicit ms/frame | Time change | Cycle change |
|---|---:|---:|---:|---:|
| Entropy | 2.5059 | 2.5670 | +2.44% | +2.67% |
| Accurate NV12 | 4.3754 | 4.4155 | +0.92% | +1.49% |
| Fast NV12 | 3.9734 | 4.0704 | +2.44% | +2.73% |

Five rotated/reversed 100-frame native rounds, then five gated PMU rounds,
CPU 0, embedded frame, no multiplexing. Positive changes mean slower.
Explicit shifts retire about 101k fewer instructions but 343k more branches
per frame. These measurements do not isolate the cause of that code-generation
change or demonstrate equivalent results on other CPUs/compilers. This version
is an experiment, not a promoted optimization.

All 332 CTest tests passed, all 120 captured frames matched, persistent decode
passed five modes, and protected source boundaries passed five images/ten
chunk sizes. Entropy and NV12 hashes agree with control.

Local assembly artifacts: `compiler-decode_mcu.asm`, `explicit-decode_mcu.asm`,
and `decode_mcu.diff`; source-annotated assembly is under `audit/`.
Raw benchmark records and medians are in `results.json` and `summary.json`.

Reproduce using the existing control/build prerequisites:

```sh
python3 test/webcam/bmi-intrinsics/build.py --only explicit-shifts
python3 test/webcam/bmi-current/audit.py --explicit-shifts
python3 test/webcam/zenjpeg-ideas/run.py --config test/webcam/bmi-intrinsics/explicit-shifts/experiment.json
```

The build script refuses to overwrite an existing candidate source directory.
