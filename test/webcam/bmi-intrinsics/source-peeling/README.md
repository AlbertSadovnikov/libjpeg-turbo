# Expressing PGO transformations directly in C

Ryzen 9 3900X, GCC 13.3 / Clang 18.1.3. No PGO or LTO. The shared
threshold-pair10 source is used with each compiler's retained baseline flags:
GCC O3 generic, Clang O3 mtune=znver2, BMI2 on jdhuff.c only.

Three source-level ideas were tested:

* **Huffman:** write the first three long-code length checks explicitly,
  followed by the original general search. No table-specific code lengths
  are assumed and the malformed-code sentinel behavior is retained.
* **IDCT:** execute the first horizontal block separately when useful_width
  is positive, then loop from block 1. Wider components and right-edge handling
  retain their general loop. SIMD IDCT kernels are unchanged.
* **Cold hints:** mark raw-output error checks, optional progress callbacks
  and suspension as unlikely, using guarded compiler builtins with a plain C
  fallback. Every check and callback remains. The predicted common case is
  the non-suspending NV12 strip decoder without a progress callback.

## NV12 timing changes against the same compiler's baseline

| Source change | GCC accurate | GCC fast | Clang accurate | Clang fast |
|---|---:|---:|---:|---:|
| Huffman peeling | +0.05% | +0.29% | -0.03% | -0.23% |
| IDCT peeling | +2.94% | -1.10% | +5.35% | +2.34% |
| Both peeling changes | -0.05% | -1.00% | +3.06% | +4.05% |
| Raw-output cold hints | -0.36% | -1.16% | +1.18% | +1.34% |

Positive means slower. The cold-hint row is a separate paired cohort; compare
changes to its own controls rather than absolute times across cohorts.

Three rotated/reversed rounds per mode, 90 preloaded frames, one full warmup
pass then three measured passes, CPU 0. Loading, allocation and hashing are
outside decode timers. All NV12 hashes match within each IDCT mode. This is
NV12-path validation only. Accurate and fast reconstruction remain separate.

The archive check verifies only jdhuff.c.o, jdcoefct-8.c.o and/or
jdapistd-8.c.o change as appropriate; all other libjpeg/TurboJPEG members
match the corresponding compiler's non-PGO control byte-for-byte. The native
C++ measurement object and embedded data are identical, and gold links every
binary. Only the target 8-bit NV12 path's wrapper objects are rebuilt.

## Interpretation

The source changes are expressible and preserve the NV12 output, but they do
not reproduce PGO's combined benefit. Explicit Huffman peeling is essentially
neutral in this test. GCC has modest fast-IDCT candidates around 1%; these
have not received bracketed final-candidate confirmation. The IDCT/combined
changes regress Clang substantially, so they are not suitable as a shared
default on this evidence.

Clang cold hints reproduce one specific PGO effect: jpeg_read_raw_data begins
with three pushes instead of five, and cold checks move after the hot return.
Full NV12 nevertheless gets slower. That is direct evidence that reproducing
a local assembly feature is insufficient to recover the PGO speedup.
Surrounding scheduling, branch weights, code layout and register allocation
remain different; we have not isolated their individual timing contributions.

No source candidate is promoted into the production codec. The same source
patches are used under GCC and Clang; the tested flags differ by compiler as
described above.

## Artifacts and reproduction

`gcc-huffman.patch` / `clang-huffman.patch`, `*-idct.patch`, `*-both.patch`
and `*-cold.patch` are source-only deltas against threshold-pair10. Compiler
pairs have the same source changes. `summary.json` / `results.json` retain
the peeling matrix; `cold-summary.json` / `cold-results.json` retain hints.
`isolation.json` checks changed archive members.

Requires the retained non-PGO controls and common NV12 driver object from
the PGO/LTO experiment. Existing candidate directories are not overwritten.

```sh
python3 test/webcam/bmi-intrinsics/source-peeling/build.py
python3 test/webcam/bmi-intrinsics/source-peeling/run.py
python3 test/webcam/bmi-intrinsics/source-peeling/build.py --only cold
python3 test/webcam/bmi-intrinsics/source-peeling/run.py --variants cold
```
