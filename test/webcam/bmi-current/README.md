# BMI instructions on the current entropy decoder

2026-10-31, Ryzen 9 3900X (Zen 2), GCC 13.3, release optimization. Unlike the
earlier `../bmi2` test on the original decoder, this targets the current winner:
scalar bulk refill + branchless two-AC-symbol LUT + pre-shifted thresholds.

**Result: BMI2 alone helps.** It reduces full-sequence accurate NV12 time
**2.13%**, fast-IDCT NV12 time **1.22%** in this experiment. Every sequence
bracket improves. BMI1/LZCNT and the combined tier do not beat BMI2 alone.

## Isolation and instruction selection

| Variant | Flags, only for jdhuff.c |
|---|---|
| Control | `-O3 -DNDEBUG`, no extra ISA flags |
| BMI1/LZCNT | `-mbmi -mlzcnt` |
| BMI2 | `-mbmi2` |
| Combined | `-mbmi -mlzcnt -mbmi2` |

Each candidate starts as a fresh build of the current source for its regression
test executables. Its codec archives are then replaced with copies of the
control archives, changing **only `jdhuff.c.o`**. Replacement objects are compiled
from the exact same absolute source path, with the same generated headers and
per-library flags as the control. Static tools are relinked against these
matched archives before correctness tests. Both `libjpeg.a` and `libturbojpeg.a`
are covered, not just whichever archive the linker happens to select first.

The original archives contain 129/157 members. Every other member is checked
byte-for-byte via SHA-256. An unfeatured recompilation reproduces the original
Huffman object byte-for-byte. `verify_isolation.py` rechecks archives after
tests/benchmarks to catch accidental rebuilds. Evidence is in `isolation.json`,
including archive/object hashes and changed-member names. Thus IDCT, packing,
other source changes, and NASM source-path metadata are excluded as independent
changes. The Huffman code's own size/layout/register allocation naturally can
change with flags.

Static instruction counts in the complete Huffman object, not dynamic counts:

| Variant | SHLX | SHRX | BZHI | ANDN | LZCNT/TZCNT/BLSR/PEXT/PDEP |
|---|---:|---:|---:|---:|---|
| Control | 0 | 0 | 0 | 0 | all zero |
| BMI1/LZCNT | 0 | 0 | 0 | 2 | all zero |
| BMI2 | 23 | 29 | 1 | 0 | all zero |
| Combined | 21 | 29 | 3 | 0 | all zero |

Counts match instruction lines only; feature words in file names are excluded.
No explicit intrinsic/algorithm change was introduced. This is compiler
instruction selection, not SIMD or a PEXT/PDEP-based decoder.

## Single embedded-frame native and hardware comparison

1920x1080 4:2:2 webcam fixture, 16,200 MCUs. Five rotated/reversed paired rounds,
100 measured frames after five warmups, CPU 0. Native runs finish before PMU
runs. FIFO-gated `cycles:u,instructions:u,branches:u,branch-misses:u` run at
100% without multiplexing. Entropy setup/abort are excluded; full NV12 includes
header/start/raw strips/packing/finish. Do not use hardware-run wall time:
it includes control FIFO waits. Native time is the median of per-trial medians;
hardware results are median per-frame counts across the five trials.

| Variant | Accurate NV12 ms | Fast NV12 ms | Accurate cycle change | Fast cycle change |
|---|---:|---:|---:|---:|
| Control | 4.3860 | 3.9769 | baseline | baseline |
| BMI1/LZCNT | 4.4291 | 4.0122 | +0.11% | +0.50% |
| BMI2 | **4.3622** | **3.9654** | **-1.63%** | **-0.54%** |
| Combined | 4.3804 | 3.9800 | -0.93% | +0.23% |

BMI2 full-NV12 cycles improve in **all five pairs** for both methods.
Accurate paired cycle reductions range 0.52–3.95%, fast 0.14–1.22%.
Isolated entropy cycles fall 1.55% and retired instructions fall **7.23%**
(20.958M to 19.443M/frame). Branch counts are essentially unchanged. Removing
instructions does not remove the serial decode dependencies or predict a
proportional cycle gain. BMI1/LZCNT's isolated entropy result improves but does
not improve complete NV12; combine feature flags only when measurements justify
it. Aggregate events do not isolate instruction latency from layout effects.

Raw values and all 120 trial records are in `summary.json` / `results.json`.
The new loop has a different result from the old original-decoder BMI test;
the previous no-gain result did not rule this one out.

## Full 120-frame sequence confirmation

Preload all frames; reuse one decoder and output buffer. Each process runs one
complete warmup pass, then three measured passes. For each IDCT mode, run three
**control → BMI2 → control** brackets. Each control value is the mean of its
two bracket endpoints, reducing slow clock/load drift. Disk reads, output
hashing, and buffer allocation are outside the per-frame timers. CPU 0.

| Mode | Control ms/frame | BMI2 ms/frame | Time reduction |
|---|---:|---:|---:|
| Accurate NV12 | 4.4040 | **4.3102** | **2.13%** |
| Fast-IDCT NV12 | 3.9244 | **3.8766** | **1.22%** |

All three brackets improve: accurate 2.47%, 1.62%, 2.30%; fast 1.10%, 1.68%,
0.87%. A complete-sequence hash of all NV12 bytes from the warmup pass matches
within every bracket. It is computed outside timing. The public prototype
`Strips::Decode` now accepts explicit JPEG bytes/length as optional arguments,
allowing real sequence replay rather than always decoding the embedded frame.
Default embedded-frame calls retain their existing behavior.

These are CPU decode results only, not GPU upload/encode timings. The scene,
CPU, clocks and code generation matter. Frequency was not fixed, and results
are not a universal guarantee across CPUs. Compare each cohort to its own
controls, not absolute times from earlier sessions.

## Correctness

All three feature builds pass 332 CTest tests each, all 120 camera frames match
the original decoded pixels, persistent reuse matches in five modes across
baseline/progressive images, and protected-page source tests match for five
images and ten chunk sizes. Full NV12 hashes match per IDCT mode in native and
hardware runs and across the replay sequence. Fast IDCT retains its previously
documented differences from accurate reconstruction; BMI2 introduces no new
pixel differences. The SIMD IDCT objects are unchanged.

## Reproduction and portability

Requires retained threshold-pair10 source/build and embedded-frame/Google
Benchmark artifacts under `/tmp`, as explicitly listed in the scripts:

```sh
python3 test/webcam/bmi-current/build.py
python3 test/webcam/zenjpeg-ideas/run.py --config test/webcam/bmi-current/experiment.json
python3 test/webcam/bmi-current/sequence.py
python3 test/webcam/bmi-current/verify_isolation.py
```

Build preparation refuses existing candidate source directories. Logs, binaries,
assembly and per-run CSVs remain local; scripts and compact JSON evidence are
versionable. The default portable codec in `src/` is unchanged. These benchmark
archives require their declared CPU features. A production portable integration
would need a detected BMI2 tier with a generic fallback; no per-symbol dispatch
or whole-program `-march=native` is needed for the idea being tested here.
