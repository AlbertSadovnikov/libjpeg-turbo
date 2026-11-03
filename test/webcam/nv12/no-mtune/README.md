# Clang and GCC without explicit CPU tuning

**No PGO, LTO enabled, no explicit `-mtune`/`-march`/`-mcpu`.** These builds
use the same stock/current source snapshots and untuned native application
support as `../lto-only/`. BMI2 on the entropy translation unit remains
matched across stock/current, as do the source's existing guarded AVX2/FMA
paths. Removing tuning does not remove those ISA-specific implementations.

## Overall JPEG → NV12

Ryzen 9 3900X, CPU 0, 1920×1080 4:2:2 capture:

| Codec compiler | Stock fast baseline | Current | Current frames/s | Latency reduction | Throughput factor |
|---|---:|---:|---:|---:|---:|
| Clang 18, ThinLTO | 4.513 ms | 3.384 ms | 295 | 25.0% | 1.33× |
| GCC 13, LTO | 4.585 ms | 3.581 ms | 279 | 21.9% | 1.28× |

Every bracket improves: Clang ranges 24.14–25.48%, GCC 21.02–22.78%.
The current Clang build averages about 5.49% lower latency than current GCC
in this alternating-order cohort. These are codec compiler comparisons with
the same native GCC C++ wrapper/driver, not independently compiled Clang/GCC
floating-point UV implementations. Clang uses ThinLTO; GCC uses its ordinary
LTO. Their LTO implementations are inherently different, but each stock/current
pair has identical compiler/flags.

Five stock/current/stock brackets per compiler; compiler order reverses each
round. Each process preloads the same 90 held-out frames and measures six
passes after full warmup. Loading, allocation and hashing are outside clocks.
No concurrent benchmark/compilation/verification. CPU frequency is not fixed.
This is one scene and one CPU. Frames/s is reciprocal mean CPU latency, not
GPU upload/encoding or multicore throughput.

Fast Y is used on both sides. Current retains the established reduced-UV
approximation, so stock/current is not byte-identical in UV. The candidate's
output contract is unchanged from previous validated experiments.

## Direct Clang tuning check

Three `znver2/default/znver2` brackets on the current pipeline, both no-PGO
ThinLTO, same sources and identical native support:

| Explicit setting | Mean ms/frame |
|---|---:|
| `-mtune=znver2` | 3.3719 |
| No `-mtune` | 3.3511 |

Default tuning is nominally 0.62% faster in this small
cohort (all three improving, 0.42–0.86%). This shows no observed need to keep
`-mtune=znver2` here, but does not establish a precise small speedup beyond
measurement noise. GCC was tested without tuning; no separate GCC tuned
reference was built. Do not infer a GCC tuning effect from the Clang result,
or compare historical cohort means to isolate tuning.

## Build, audit and validation

All four codec archive sets are fresh builds. Flags are
`-O3 -DNDEBUG -flto=thin` (Clang) or `-O3 -DNDEBUG -flto` (GCC); both append
`-mbmi2` to `jdhuff.c` only. No generation/use/sample profile flags or profile
files are used. The same shared GCC O3 native drivers, fusion wrapper, frame
object and NASM kernels are verified against the prior no-PGO support hashes;
those support objects also have no `-mtune`. Keeping the wrapper unchanged
preserves UV rounding (Clang compilation of that wrapper previously changed
a few sample-rounding outcomes).

Compile-command audits parse option tokens rather than matching path names.
Every codec C command has LTO and no explicit tuning/profile flags. Clang
bitcode members have no ProfileSummary or instrumentation. GCC ELF LTO
members are checked through their serialized options, and final binaries
have no profiling runtime symbols. GCC serializes its normal implicit
`-mtune=generic` default into LTO metadata; this is not an explicitly passed
tuning option or a Zen-specific setting. Native archive members are SIMD
assembly. Full counts/hashes are retained in `audit.json`.

Both compilers match all existing output oracles: stock on 120 captures,
current on all 120 captures, six boundary fixtures and mixed table-change
sequences, both IDCT modes, padded/unaligned output and untouched padding.
Historical oracles are data only; no PGO binary is executed in this experiment.

## Reproduce and selected artifacts

```
python3 test/webcam/nv12/no-mtune/build.py
python3 test/webcam/nv12/no-mtune/audit.py
python3 test/webcam/nv12/no-mtune/run.py
python3 test/webcam/nv12/no-mtune/clang-reference.py
python3 test/webcam/nv12/no-mtune/select.py
```

Preferred untuned Clang executable: `/tmp/mjpeg-no-mtune/nv12`; its archives
and binary are also under `/tmp/mjpeg-no-mtune/candidate/`. GCC's current
executable remains `/tmp/mjpeg-no-mtune/gcc/current/nv12`. Previous tuned
artifacts are preserved for reproduction. `preferred-candidate.json` records
current flags, hashes and selection limits; no quantizer cache is selected.

Requires source snapshots/native support under `/tmp/mjpeg-lto-only`, the
capture, fixtures and benchmark support from the restart plan. The Clang
tuning check uses the previous no-PGO tuned executable only. Generated
codecs/logs/audit objects stay under `/tmp/mjpeg-no-mtune`; compact evidence
and every raw timing round stay here. Production `src/` and `simd/` are
unchanged. No commit or push.
