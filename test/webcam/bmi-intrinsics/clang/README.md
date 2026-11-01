# Clang versus GCC and explicit BMI operations

2026-10-31, Ryzen 9 3900X, Ubuntu Clang 18.1.3 versus GCC 13.3.
All use `-O3 -DNDEBUG`, with `-mbmi2` on jdhuff.c only. No native-CPU flags.
Three full Clang builds were prepared from the same threshold-pair10 decoder:
ordinary C, the explicit SHRX/SHLX patch, and the explicit BZHI patch.

For the Clang candidate archives, every member except jdhuff.c.o was copied
from the full Clang control and verified identical. The GCC reference is the
existing GCC BMI2 build. Thus Clang-to-Clang comparisons isolate the entropy
source change; GCC-to-Clang comparisons include compiler changes throughout
the codec. Benchmark drivers and embedded input are identical across variants.

## Results

| Build | Entropy ms | Accurate NV12 ms | Fast NV12 ms |
|---|---:|---:|---:|
| GCC ordinary C | 2.4934 | 4.4079 | 4.0015 |
| Clang ordinary C | 2.5542 | 4.5293 | 4.2021 |
| Clang explicit SHRX/SHLX | 2.5798 | 4.5230 | 4.2153 |
| Clang explicit BZHI | 2.6024 | 4.4802 | 4.1412 |

Relative to Clang ordinary C, explicit shifts change entropy time by +1.01%,
accurate NV12 by -0.14%, and fast NV12 by +0.31%. Entropy cycles increase
0.65%. Explicit BZHI changes entropy time by +1.89%, accurate by -1.08%,
and fast by -1.45%; entropy cycles increase 1.79% while full NV12 cycles
decrease about 1.5%. These mixed results do not establish a consistent benefit.
Positive changes mean slower. No candidate is promoted.

Five rotated/reversed 100-frame native rounds, followed by five gated PMU
rounds, CPU 0, embedded webcam frame; counters were not multiplexed. The CPU
frequency was not fixed. Small full-pipeline differences need confirmation
before treating them as improvements.

Each Clang build passed 332 CTest tests, exact pixels for all 120 captured
frames, persistent decoding in five modes with mixed images, and guarded
source reads on five images with ten chunk sizes. Entropy and NV12 hashes
agree. Helper checks also cover 131,070 amplitude cases and 4,096 shift pairs
in generic/BMI2 builds and AT&T/Intel assembly dialects (helper-checks.json).

## Disassembly

| Clang variant | SHRX | SHLX | BZHI |
|---|---:|---:|---:|
| Ordinary C | 17 | 8 | 4 |
| Explicit shifts | 17 | 12 | 0 |
| Explicit BZHI | 17 | 8 | 4 |

These are static instruction sites in the combined fast/slow `decode_mcu`
function, not executed counts. Clang's debug inline attribution differs among
variants, so these totals are more comparable than fast-only source labels.
Every source-mapped debug object has executable text identical to its measured
release object (`isolation.json`).

Clang already emits SHRX/SHLX and fuses some shifts/masks into BZHI from C.
The explicit shift wrappers retain the opcodes but hide those operations from
the optimizer, preventing that fusion. The BZHI intrinsic retains the same
opcode counts in decode_mcu; the complete executable text still differs,
including the slow helper, register allocation and layout.

There are no public SHRX/SHLX intrinsics in these installed GCC and Clang BMI2
headers. Our wrappers use GNU inline assembly and compile under both compilers.
They guarantee those operations but are opaque to optimization. `_bzhi_u32`
is an actual intrinsic recognized by both compilers, and permits more compiler
reasoning about its result. Either implementation still needs BMI2 runtime
dispatch before use in a portable binary.

Local disassembly: `clang-control.asm`, `clang-explicit.asm`, `clang-bzhi.asm`.
Diffs: `clang-explicit.diff`, `clang-bzhi.diff`; source-annotated files have
the `-source.asm` suffix. No production codec source was changed.

## Reproduce

Existing threshold-pair10, explicit-shifts and bzhi-mask source trees plus
Google Benchmark artifacts are prerequisites, as in the parent experiment.
The build script refuses to overwrite existing Clang source/build directories.

```sh
python3 test/webcam/bmi-intrinsics/clang/build.py
python3 test/webcam/zenjpeg-ideas/run.py --config test/webcam/bmi-intrinsics/clang/experiment.json
```

Build isolation and assembly metadata are in `isolation.json`; raw timing and
counter records in `results.json`; medians and validation in `summary.json`.
