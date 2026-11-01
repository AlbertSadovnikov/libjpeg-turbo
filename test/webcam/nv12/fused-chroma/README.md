# Fused chroma reconstruction to NV12

Prototype for the captured 1920x1080 4:2:2 MJPEG stream, Ryzen 9 3900X.
Two Cb/Cr 8x8 blocks become one interleaved 8x4 chroma block directly.
There is no separate full-height U/V reconstruction buffer or packing pass
on the fused path. Luma keeps the existing selected IDCT method.

## Final comparison against the retained Clang PGO+ThinLTO decoder

| Variant | Bracketed native control | Fused | Time reduction |
|---|---:|---:|---:|
| Accurate Y + exact chroma | 4.284 ms | 4.067 ms | 5.06% |
| Accurate Y + reduced chroma | 4.312 ms | 3.965 ms | 8.03% |
| Fast Y + reduced chroma | 3.901 ms | 3.688 ms | 5.46% |

Three control-candidate-control brackets per case; candidate order alternates.
All nine brackets improve. Exact accurate reductions range 3.89–6.74%;
reduced accurate 5.11–12.35%; reduced fast 4.97–5.77%. The accurate reduced
mean includes a larger first-bracket improvement; timing is not a universal
8% guarantee. A prior integration cohort also improved in all brackets.

Each process preloads 90 held-out frames, performs a complete warmup pass,
then measures three full passes. CPU 0. Loading, allocation and hashing are
outside timers. CPU frequency was not fixed. This is JPEG-to-NV12 only.

The source/driver object is identical between control and candidate. Candidate
archives retain the previous PGO+ThinLTO objects except jdcoefct-8.c.o, which
is rebuilt with ThinLTO but without its now-stale profile. The new kernel is
a normal GCC-compiled AVX2/FMA object plus NASM. All other archive members
are checked byte-for-byte. The new scheduling path has not been re-trained
with PGO; these are integration measurements, not a wholly re-profiled build.

## Output quality

All 120 captured frames, accurate and fast luma modes:

* Exact accurate fusion matches every NV12 byte. Fast mode uses the ordinary
  implementation for the exact variant; a fused exact fast-IDCT kernel was
  not implemented or claimed as a speedup.
* Reduced fusion leaves luma byte-identical to the selected native method.
* Reduced UV versus native **accurate IDCT plus averaging**: maximum error 1,
  mean absolute error 0.109656 levels, 10.9656% of samples changed, mean signed
  error -0.109600. These are 8-bit sample levels, and apply to this capture.
* Reduced UV is the same regardless of the luma IDCT choice. Compared with
  native fast-IDCT chroma, maximum difference is 2; compared with accurate
  chroma it remains 1. Native fast chroma itself differs more from accurate
  on this capture.
* Padded, deliberately unaligned Y and UV strides match tight output and leave
  row padding unchanged.

Synthetic UV kernel checks cover 10,000 pairs, including zero, horizontal,
vertical, sparse, dense and clipping-heavy coefficients: exact output matches
native accurate IDCT followed by byte averaging/interleaving. A separate
double-precision inverse-transform/vertical-average oracle checks 500 pairs
for the reduced kernel, with maximum difference 1. Output padding is checked.

Reduced fusion averages before final sample rounding/clipping; exact fusion
averages already rounded/clipped bytes. They are different output contracts.
The one-level bound on this capture is not a bound for arbitrary JPEG data
with strong clipping. No approximate mode was made a production default.

## Implementation

**Exact, exact.asm:** reuse the repository's accurate AVX2 IDCT arithmetic.
After each transform, average adjacent byte rows. Keep Cb results in
xmm12–15 across the Cr transform, then interleave and write four UV rows.
This removes full-height planar stores, pointer traffic, separate packing
and some dispatch overhead, while retaining native rounding and clipping.

The original single-block routine starts with legacy SSE loads on clean YMM
state. Inside our paired routine the Cr pass follows AVX2 work; those loads
are changed to VEX encodings. The initial uncorrected version suffered a
large regression. The exact body is generated from jidctint-avx2.asm, retaining
its source/license header and original arithmetic constants.

**Reduced, fusion.cc:** process Cb and Cr in separate 128-bit halves of AVX2
float vectors. Cached quantization-weighted vertical matrices directly compute
the four adjacent-row averages. All vertical frequencies contribute except
frequency 4, whose contribution cancels; this is not simply discarding the
upper half of the DCT coefficients. A factored LL&M horizontal IDCT runs on
four rows per component. Vector transposes, clipping, byte packing and UV
interleaving finish with four 16-byte stores. No extra work is put into the
serial Huffman loop.

**Scheduling:** an isolated hook after an MCU's entropy decode performs the
two native Y IDCTs and invokes the paired chroma kernel. A benchmark-only
thread-local registration provides the UV destination/stride. The ordinary
raw path remains the fallback. Guards require 8-bit interleaved full-size
4:2:2 Y/Cb/Cr in the expected scan order, complete 16x8 MCUs, and supported
CPU features. Geometry/scan layouts outside this prototype remain on the
existing decoder path. The NV12 driver skips its ordinary packing only when
fusion is registered successfully.

This is an x86-64 SysV AVX2/FMA experiment, not a public NV12 API. The hook
and thread-local registration are benchmark integration scaffolding. Production
codec sources and default APIs are unchanged; no commit was made.

## Artifacts and reproduce

* `fusion.cc`, `exact.asm`: the paired kernels.
* `codec-hook.patch`: source delta against threshold-pair10.
* `driver.cc`, `prepare_driver.py`: matched NV12 integration/validation.
* `pgo-summary.json`, `pgo-results.json`: final bracketed comparison.
* `pgo-validation.json`: full capture error and hash records.
* `kernel-summary.json`: independent kernel checks.
* `artifact-summary.json`: final binary/object/source hashes.
* Earlier GCC-only and pre-guard records are retained as exploratory cohorts;
  the final figures above come from pgo-summary.json.

Requires retained compiler/Google Benchmark/capture artifacts from the prior
experiments. Preparation writes only the isolated /tmp source/build tree.

```sh
python3 test/webcam/nv12/fused-chroma/build.py
python3 test/webcam/nv12/fused-chroma/prepare_driver.py
python3 test/webcam/nv12/fused-chroma/check.py
python3 test/webcam/nv12/fused-chroma/run.py
python3 test/webcam/nv12/fused-chroma/pgo.py
```
