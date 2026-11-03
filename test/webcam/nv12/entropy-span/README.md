# Precomputed two-symbol coefficient advance

> Historical PGO-assisted cohort. The user now requires no PGO in comparisons,
> with LTO allowed. Use [the matched LTO-only report](../lto-only/README.md) for
> current overall numbers and selection; the original evidence below is preserved.

Step 4 of the agreed plan: inspect refill/LUT/bit-count/store dependencies,
then test one small entropy source change. The earlier quantizer-cache
experiment was not selected. Both cases here retain the user's inline AVX2
zeroing preference, register-rewritten paired Y, and existing reduced UV.
Production `src/` and `simd/` are unchanged.

**Decision:** select the span candidate and keep inline AVX2 zeroing. It
improves all five matched-source brackets (−1.06% mean) and all five direct
confirmation brackets against the previous selection (−2.29%). The quantizer
cache is excluded. Output and every serialized coefficient remain unchanged.

## Evidence and change

The retained Clang native annotated control shows the fused-hit guard loading
`step1` and `step2` from entry offsets 5 and 6, computing `k+step1`, adding
`step2`, then checking against 64. Coefficient stores additionally need the
first and last zigzag positions. LUT lookup and refill remain on the serial
reservoir/consumed-bit-count chain; broader early lookahead was already tested
in `../lut-pipeline/` and is not repeated here.

`span.patch` reuses the unused `count` byte (offset 7) as `span=step1+step2`.
The table builder fills it once per entry. Entries stay eight bytes; there
are still 1,024 entries per table. Valid advances are 1–32, so UINT8 suffices.
The guard uses `next_k=k+span`, and that same value supplies the last-store
and next-iteration index. `step1` is needed only for the first store and can
be loaded after the guard. No extra LUT, larger lookahead, new refill scheme,
new block specialization or coefficient-layout change is introduced.

Single-symbol hits still repeat the same store. EOB, ZRL, long codes, the
slow decoder, restart handling, marker rollback and bit consumption are
unchanged. Prefix entries that would cross the block boundary still fall
back. All cache invalidation keys and table sizes remain the same.

Actual profiled assembly confirms offset-6 step2 loads leave the hot path and
an offset-7 span load feeds a single addition before the guard. The offset-5
step1 load moves after the successful guard. The active decoder is selected
by following the pointer set in exported `jinit_huff_decoder`; the executable
contains other same-named private functions that must not be mistaken for it.

| Assembly scope | Control decode bytes | Span decode bytes |
|---|---:|---:|
| Clang native O3 unprofiled diagnostic | 5,494 | 5,398 |
| GCC native O3 unprofiled diagnostic | 7,030 | 7,036 |
| Actual native Clang PGO pipeline | 6,202 | 6,237 |

The two actual profiled decoders each have 192 static stack-memory operand
sites. These code-size/load-site observations do not attribute exact cycles
or dynamic spills. GCC diagnostics are not a GCC timing result.

## Matched profiles and object isolation

Each source is independently trained on the same first 30 capture frames,
through the actual selected NV12 path in both IDCT modes, one measured pass
plus the driver's warmup. The remaining 90 frames are held out. Final entropy
objects use identical Clang O3, mtune=znver2 and BMI2 flags with their own
fresh profiles. No old CFG profile is supplied to the new decoder.

Fresh entropy-only ThinLTO bitcode could not import retained codec bitcode:
LLVM rejected their conflicting `ProfileSummary` module flags. That failed
link occurred before candidate timing. Both entropy variants therefore use
**native profiled objects**, while all other archive members retain their
original ThinLTO/PGO bytes. Only `jdhuff.c.o` changes in each of `libjpeg.a`
and `libturbojpeg.a`. This is a matched partial rebuild, not a fully rebuilt
or fully reprofiled codec. `thinlto-note.json` records the constraint.

A separate direct comparison against the previous selected executable checks
whether the changed native/profile regime loses against the actual preferred
baseline. That comparison includes the regime change; the matched-profile
cohort is the source-change comparison. Do not subtract independent cohorts
to claim an exact LTO/profile contribution.

## Validation

Both independently profiled sources match retained selected full NV12 reports
on all 120 captures, six fixtures (`rst1`, `optimized`, `progressive`, `dense`,
`tail63`, `zeroac`), accurate and fast IDCT modes, unaligned/padded destinations
and unchanged padding. A mixed sequence alternates capture, DQT mutations,
optimized/different Huffman tables, restart and progressive inputs and then
returns to previous tables within one decoder, exercising cache invalidation
and unchanged fallback paths.

For every capture, fixture and both DQT mutations, separate control/candidate
processes also serialize every quantized coefficient and quantizer table.
The runner compares the full binary outputs **literally byte-for-byte**, then
discards the large streams and saves SHA-256 evidence. This validates values
before IDCT; it is not just a final-MCU or frame hash. The coefficient-API
reader's unused raw-output fusion hook returns zero and does not alter entropy.
The normal NV12 executable retains the selected fusion path.

No changed IDCT arithmetic is introduced here; the prior register-kernel
captured/synthetic checks remain applicable. This is targeted valid-input
coverage, not an exhaustive malformed-JPEG test.

## Initial matched-profile cohort

| Five brackets | Control | Candidate | Change | Improving |
|---|---:|---:|---:|---:|
| Span versus matched original | 3.4214 ms | 3.3853 ms | −1.06% | 5/5 |
| Byte-identical original noise control | 3.3994 ms | 3.4053 ms | +0.17% | 3/5 |
| Previous selected executable versus rebuilt original | 3.3987 ms | 3.4203 ms | +0.64% | 2/5 |

Span changes range −1.98% to −0.08%; identical-code changes range −0.95% to
+1.34%. The selected-versus-rebuilt range is −1.16% to +2.92%. These are raw
observations, not confidence intervals. Preserve all noisy rounds. The
matched result justifies a direct confirmation against the previous selected
binary rather than selecting from means across separate comparisons.

CPU 0, five control/candidate/control brackets per case, candidate/noise/old
selection order reverses on alternate rounds. Each process preloads 90 held-out
frames and measures three passes after a full warmup. Setup/finish and any
cache setup are included; loading/allocation/hashing are outside clocks.
Frequency is not fixed. No benchmark process runs concurrently with compilation
or coefficient verification. This is one captured scene on one CPU.

## Direct confirmation and selection

| Five longer brackets | Previous selected control | Candidate | Change | Improving |
|---|---:|---:|---:|---:|
| Span, including new profile/native build | 3.3966 ms | 3.3188 ms | −2.29% | 5/5 |
| Byte-identical previous-selection noise control | 3.4081 ms | 3.4278 ms | +0.58% | 3/5 |

Six measured passes after warmup, same 90 held-out frames, CPU 0, alternating
span/noise bracket order. Span changes range −3.46% to −1.05%; identical-code
changes range −0.63% to +2.83%. The repeated direction supports retaining this
experimental candidate, while the large noise and single scene/CPU limit
its precision and portability. No fixed 2.29% guarantee is claimed.

The direct confirmation includes a new profile and native entropy object;
**do not attribute the full 2.29% to the span byte alone**. The independent
matched-profile cohort measures about 1.06% for the source change. Do not add
these percentages or subtract independent cohort means as exact accounting.

Selected executable: `/tmp/mjpeg-entropy-span/nv12`; its archives and binary
are also under `/tmp/mjpeg-entropy-span/candidate/`. `select.py` verifies the
built and confirmed hashes before creating these aliases; it preserves the
previous selected executable for reproduction. `preferred-candidate.json`
records the complete selected pipeline and limitations.

## Reproduce

```
python3 test/webcam/nv12/entropy-span/build.py
python3 test/webcam/nv12/entropy-span/audit.py
python3 test/webcam/nv12/entropy-span/run.py
python3 test/webcam/nv12/entropy-span/confirm.py
python3 test/webcam/nv12/entropy-span/select.py
```

Build uses retained selected codec archives, wrappers, benchmark driver,
embedded object, capture and fixtures listed in the restart plan. It refuses
to mix existing raw profiles with a fresh training run; use a new profile
location for a new cohort. Changed-table fixtures come from `quantizer-cache/run.py`.
Generated sources, libraries, profiles, binary streams and full disassembly
stay under `/tmp/mjpeg-entropy-span` (streams are compared in memory).
Compact source patch, scripts, profile/build hashes, complete validation,
coefficient hashes and every timing round are retained here. No commit/push.
