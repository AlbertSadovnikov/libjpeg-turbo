# libc memset in the hot MCU path

> Historical PGO-assisted cohort. The user now requires no PGO in comparisons,
> with LTO allowed. Use [the matched LTO-only report](../lto-only/README.md) for
> current overall numbers and selection; the original evidence below is preserved.

Follow-up to `../coefficient-cost/`: distinguish a costly call boundary from
writing the 512-byte coefficient buffer. Ryzen 9 3900X, CPU 0; same retained
PGO/ThinLTO codec, register-rewritten paired Y, and reduced UV. Production
sources remain unchanged. No commit or push is made.


**Result:** direct libc clearing is about 4.1 ns/MCU (~0.067 ms/frame).
Forced SSE2 inlining regresses full NV12 by 4.21%; inline AVX2 has no reliable
win beyond the identical-binary noise control. **The user nevertheless prefers
inline zeroing, so guarded inline AVX2 is the selected experimental candidate.** All variants
preserve current output on the capture and fixture validation.

## Corrected assembly attribution

The final executable contains two private `decompress_onepass` functions.
The earlier audit selected the first, unfused one. `audit.py` here selects
the function that calls `mjpeg_fusion_mcu`. **The active fused controller
already calls libc `memset` directly:** ThinLTO imports and folds the
`jzero_far` wrapper. Its explicit direct-libc replacement produces an
entire executable with the **same SHA-256** as control. We retain timed
comparisons of these identical binaries as a useful noise control, not an
implementation gain. The earlier report and audit were corrected; no earlier
timing data was changed.

## Isolated costs

The size is runtime-opaque to the compiler for the dynamic cases. Each
operation clears the same reused buffer, warmed before clocks. A compiler
memory barrier after every iteration prevents dead-store removal. The actual
MCU alignment is offset 32 within a 64-byte line; aligned and offset-1 rounds
are also retained in `micro-results.json` / `micro-summary.json`.

| Operation, offset 32 | Mean ns/iteration | Equivalent at 16,200 MCUs/frame |
|---|---:|---:|
| Opaque `jzero_far` call → libc | 4.171 | 0.0676 ms |
| Direct dynamic libc `memset` | 4.114 | 0.0666 ms |
| Forced inline 512-byte clear, generic SSE2 | 7.377 | 0.1195 ms |
| Guarded inline AVX2 clear | 4.113 | 0.0666 ms |
| Opaque empty call | 1.169 | 0.0189 ms |
| Inline compiler barrier only | 0.238 | 0.0038 ms |

Five rotated/reversed rounds, each batch >=0.15 s, CPU 0. These numbers
include loop/barrier overhead and are throughput measurements of repeated
operations. An empty call puts the boundary scale in context; its difference
from a barrier is about 0.93 ns (~15 microseconds/frame). **It is not an
exact marginal cost to subtract from libc clearing.** The writes, call,
register allocation, and subsequent entropy work can overlap differently.
Hot PLT/IFUNC resolution is warmed, not repeatedly charged as first-call cost.

The generic compiler target emits 32 16-byte SSE stores for forced inlining.
The guarded AVX2 path emits 16 32-byte stores, plus the size/CPU checks and
`vzeroupper`. All stores support unaligned addresses and cover exactly the
original 512 bytes. Both fixed paths fall back to the original routine for
other lengths; AVX2 additionally falls back on unsupported CPUs. No global
AVX2 flags were added to the controller. Controller sizes are 861 bytes
(control/direct), 1,104 (SSE2 inline), and 1,040 (AVX2 inline). All have 35
static stack-memory operand sites; removing the clear call did not eliminate
those sites. These are static observations, not dynamic spill-cost counters.

## Full-path result

| Comparison | Bracketed control | Candidate | Mean change | Improving brackets |
|---|---:|---:|---:|---:|
| Direct libc (identical executable; noise control) | 3.3662 ms | 3.3496 ms | −0.49% | 4/5 |
| Forced inline SSE2 | 3.3595 ms | 3.5010 ms | +4.21% | 0/5 |
| Guarded inline AVX2 | 3.3616 ms | 3.3431 ms | −0.55% | 4/5 |

The identical-binary comparison ranges from −1.87% to +0.20%. Its apparent
speedup is measurement variation, not an optimization. The AVX2 result
(−1.21% to +0.17%) is comparable in scale and direction, so this cohort does
not establish a reliable net improvement. SSE2 inlining consistently regresses
(+2.91% to +5.04%); its pipeline penalty exceeds the isolated clear difference,
illustrating why the microbenchmark is not exact additive accounting.

**Selection updated by user preference:** use guarded inline AVX2 for the
512-byte MCU clear, even without a demonstrated speedup. The call boundary can matter, but here a hot
512-byte libc clear costs about 4.1 ns including the stores, and forced
inlining does not establish a better full-path result. Selection does not
change that finding; do not pool its apparent gain with the previous IDCT improvement.
A smaller benefit remains possible; demonstrating it would need tighter
measurement conditions or a later independent cohort. These results do not
say libc calls are cheap for every size, caller, or CPU.

## Full-path experiment and validation

Only `jdcoefct-8.c.o` is replaced in each of `libjpeg.a` and `libturbojpeg.a`.
All other members are checked byte-for-byte. Every controller uses the same
Clang O3/ThinLTO flags without PGO, as in the existing fusion build; all other
codec PGO profiles are preserved. Full-path wrappers, IDCT and UV objects are
identical across cases. No stale profile is applied to changed controller CFG.

All four variants match the retained best complete NV12 validation reports
on 120 captures and six fixtures (`rst1`, `optimized`, `progressive`, `dense`,
`tail63`, `zeroac`), both IDCT modes, padded/unaligned destinations and unchanged
padding. Separately, the clear helpers pass 2,816 byte-by-byte guard tests:
every offset 0–63 and lengths 0–1,280 in 128-byte increments, all four helpers.
The current CPU executes the AVX2 fast case; a CPU without AVX2 was not available.
No clear is omitted and no stale coefficients are supplied to IDCT.

Five control/candidate/control brackets per variant, rotating candidate order,
90 preloaded held-out frames, three passes after complete warmup. Allocation,
input loading, hashing and validation are outside timers. No concurrent
compilation or CPU-heavy verifier. Frequency is not fixed. This is one scene
on one CPU; differences between whole-path and isolated costs are not exact
additive accounting.

## Reproduction

`clear.h` defaults to the AVX2 variant when no experiment override is supplied.
`build.py` builds the matched controls and selects AVX2 using `select.py`.
The selected executable is `/tmp/mjpeg-memset-call/nv12`; its codec archives
and executable are also available through `/tmp/mjpeg-memset-call/candidate/`.
`preferred-candidate.json` records the choice and exact artifact hashes.
The fallback for unsupported CPUs and other MCU sizes remains unchanged.

```
python3 test/webcam/nv12/memset-call/build.py
python3 test/webcam/nv12/memset-call/audit.py
python3 test/webcam/nv12/memset-call/micro.py
python3 test/webcam/nv12/memset-call/run.py
# Select already-built, validated artifacts without rebuilding or retiming:
python3 test/webcam/nv12/memset-call/select.py
```

Requires retained capture, six fixtures, PGO/ThinLTO archives and drivers from
the preceding experiments, including `/tmp/mjpeg-coefficient-cost`'s register
kernel and GCC wrapper. New generated files stay in `/tmp/mjpeg-memset-call`.
`controller.patch` and `clear.h` are the reviewable source change; build,
assembly, validation, raw timings, and summaries are retained alongside this
report. The reconstructed control is validated against the prior best output.
