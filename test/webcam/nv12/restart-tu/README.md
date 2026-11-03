# Isolate restart entropy decoding in a native translation unit

The ordinary entropy routine now has the **same normalized instructions as
the original control under both compilers**. Logitech's fixed balanced repeat
shows no repeatable regression (Clang -0.62%, GCC -0.02%, comparable to timing
noise), while LifeCam retains 23.25% / 26.97% less decode time versus the prior
optimized path. All measured cohorts, including noisy/slower ones, are kept.
This is a separate experimental exact-output candidate, not a changed default.

## LifeCam 1080p: independent long confirmation

| Compiler | Previous optimized | Isolated restart TU | Less time |
|---|---:|---:|---:|
| clang | 5.3739 ms | 4.1244 ms | 23.25% |
| gcc | 5.4868 ms | 4.0069 ms | 26.97% |

Three control/candidate/control brackets, sixty timed passes over twelve
preloaded real LifeCam frames per invocation. Every bracket improves.
The old codec remains Clang ThinLTO/GCC LTO. Only the **new** restart unit is
compiled O3/BMI2 with `-fno-lto` to enforce the optimization boundary. There
is no PGO, no explicit mtune/march/mcpu, and no removal of default protections.
Shared native Y/UV/packing and driver objects remain identical.

## Logitech 1080p: balanced regression check

Negative means less time; these small means are not new speedup claims:

| Compiler | Original | Candidate | Time change | Identical-binary noise mean |
|---|---:|---:|---:|---:|
| clang | 3.5400 ms | 3.5182 ms | -0.62% | +0.64% |
| gcc | 3.5553 ms | 3.5545 ms | -0.02% | -0.13% |

Five predetermined ABBA/BAAB brackets per compiler, sixty passes over twelve
frames per process, with compiler order alternating. A=original, B=candidate;
ABBA runs A/B/B/A and BAAB the reverse. Two additional sham brackets per
compiler use the original executable for both A and B. Both signs occur in
the candidate rounds. No reliable Logitech slowdown is established by this
repeat, and no claim of exactly zero overhead is made.

### Earlier cohorts remain visible

| Compiler | Initial brackets | First long confirmation | Balanced repeat |
|---|---:|---:|---:|
| clang | +1.03% | +3.29% | -0.62% |
| gcc | -0.21% | -0.05% | -0.02% |

The first long Clang confirmation includes a +8.45% bracket; its adjacent GCC
control interval was also slower than the later baseline intervals. The cause
of the transient was not measured. Rather than deleting that observation or
pooling incompatible schedules, `balanced.py` repeats the regression question
with fixed ABBA/BAAB order and same-binary controls. Its complete five rounds
are retained, including both faster and slower results. Thus the conclusion
is no *repeatable* regression after isolation, not a proof inferred solely from
identical instructions or a claim that every timing invocation improved.

Primary `results.json` also includes a linked-but-unused-extension control at
Logitech 1080p. That control retains the original core archives and never
selects the new decoder. It helps distinguish the presence/layout of the new
object from the scan-selection hook; its small timing differences are context,
not proof of a particular cache or branch-predictor cause.

## Actual implementation boundary

The original entropy source gains only a forward declaration and a small
start-pass hook. On every sequential scan it resets `decode_mcu` to the
original function, then calls `mjpeg_restart_select` only if DRI is nonzero.
Resetting per scan handles DRI changes on persistent decoder reuse. The
original fast/slow routines remain in their original TU with their original
call graph. A scan's MCU callback points directly at the selected routine;
there is no additional wrapper call per MCU.

The separate native TU contains the validated restart-aware reader, slow
fallback and marker/DC-reset handling. Its copies of fill/huffman helpers have
private experimental names, preventing new native references to the original
LTO helpers. A literal copy of the **standard JPEG zigzag order** is also kept
private. This is not a camera Huffman table or feed specialization.

That last detail mattered: the first split-TU build still referred to
`jpeg_natural_order`, and GCC changed its ordinary entropy code even in the
linked-but-unused control (1,647 → 1,673 instruction sites). After eliminating
that shared reference, GCC returns to 1,647 sites and identical normalized
instructions; Clang retains 1,342 throughout. Initial assembly metadata and
native source/object snapshots are saved for this untimed setup investigation.
No first-setup timing was used as a final result.

`audit.py` follows the actual jinit pointer for the ordinary routine and the
native selector for the restart routine. It normalizes only relocations,
private LLVM name suffixes and local target addresses; this is not a claim
of byte-identical full executables. Both reference executables, however, are
byte-identical to the existing multi-camera baseline binaries. The core
archives replace only jdhuff.c.o; the new native object is linked separately.
Archive/binary hashes and absent PGO metadata are checked. The source prefix
and private state layout are generated from the exact host source/config;
production integration would need a maintained shared private interface.

## Algorithm and validation

The restart algorithm is unchanged from the validated restart-fast experiment:
use fast attempts before the last MCU in an interval; retain its conservative
source-byte budget and final-MCU slow path. Marker lookahead aborts before
fabricating bits or committing source/bit/DC state. Clear partial coefficients
per block and replay slowly, without assuming virtual coefficient arrays are
contiguous. Constant retry clears stay inline; original AVX2 controller clear
is unchanged. This is single-threaded; row parallelism was not attempted.

The final native-unit build passes, with both compilers:

- All 2,148 new camera frames over 179 modes / 29 resolution-camera groups,
  compared to saved stock-fast-exact NV12 output reports; accurate/fast methods,
  modes 1/2/3, generic edge fallbacks and untouched strided padding.
- The 51 existing restart fixtures: DRI 1,2,3,7,31,119,120,121,241,65535;
  ordinary/dense/zero-AC/high-frequency-tail coefficients; optimized tables;
  legal FF fill bytes before restart markers. Inputs are coefficient-preserving
  transcodes, not RGB conversions or pixel re-encoding.
- Alternating cameras and mixed restart/non-restart/progressive frames in
  persistent decoders, verifying table and callback refresh.
- 2,325 literal coefficient/table streams against the original reference,
  including noncontiguous full-image coefficient arrays.
- Full versus suspended arrays on 23 inputs, 97/4093-byte reveal increments,
  with 127,934 forced entropy/marker suspensions per compiler/harness run.
  Control/candidate hashes agree. Header/progressive startup suspension and
  exhaustive malformed-input behavior are outside this claim.

The untimed native-TU diagnostic confirms it is never entered on Logitech,
and commits 98.77% of LifeCam's 194,400 sampled MCUs through the fast path,
with seven marker retries. Sparse/fill fixtures exercise thousands of retries.
It is a counter build that skips reconstruction, not timed NV12 or PGO.

## Primary stock-fast comparisons

| LifeCam size | Compiler | Stock fast → candidate | Less time |
|---|---|---:|---:|
| 640x480 | clang | 1.2363 → 0.8767 ms | 29.09% |
| 640x480 | gcc | 1.2867 → 0.8701 ms | 32.38% |
| 1280x720 | clang | 3.7281 → 2.6084 ms | 30.04% |
| 1280x720 | gcc | 3.9331 → 2.6034 ms | 33.81% |
| 1920x1080 | clang | 6.3236 → 4.1857 ms | 33.81% |
| 1920x1080 | gcc | 6.4717 → 4.0852 ms | 36.88% |

These are three-bracket, twenty-pass primary measurements with identical
output hashes and matched per-compiler feature tiers. They are separate from
the long optimized-versus-optimized confirmation. They must not be added to
previous speedup percentages or substituted into older single-scene timings.

All measurements pin CPU 0 on the same Ryzen 9 3900X. Files are preloaded,
output is warmed, and loading/allocation/hash work is outside decode timing.
Case order rotates; all rounds are retained. No build, verification or profiler
runs concurrently with timing. Machine frequency is not fixed; one CPU and
short real input sequences remain coverage limits. No GPU/encoder throughput
claim follows from these CPU decode measurements.

## Remaining short-interval limits

Three brackets per scene, fifty passes each; positive means slower:

| Scene | Clang time change range | GCC time change range |
|---|---:|---:|
| dense-rst2.jpg | -30.70% to -27.61% | -31.38% to -25.18% |
| ordinary-fill-rst3.jpg | -12.75% to -11.45% | -18.72% to -13.91% |
| ordinary-rst1.jpg | +3.43% to +6.39% | -0.21% to +0.61% |
| ordinary-rst2.jpg | -9.87% to -9.35% | -13.87% to -12.27% |
| zeroac-rst3.jpg | +6.53% to +7.97% | +6.07% to +7.16% |

The sparse DRI-3 case still regresses about 6–8%, and Clang's fully slow DRI-1
case also regresses. Isolation addresses the ordinary non-restart code-generation
coupling; it does not solve every restart-workload tradeoff. Dense DRI-2 gains
remain large. Keep this a separate prototype, with prior defaults unchanged,
until short/sparse behavior and broader scene/CPU coverage are addressed.
No accuracy or output-contract relaxation was introduced to obtain the gains.

## Files and reproduce

`candidates.json` records `/tmp/mjpeg-restart-tu/clang-nv12` and `gcc-nv12`,
with explicit arguments `fast 3 PASSES JPEG...` and hashes. Earlier exact-fast,
reduced-UV, GCC-deferred and restart-fast aliases remain untouched.

```
python3 test/webcam/nv12/restart-tu/build.py
python3 test/webcam/nv12/restart-tu/audit.py
python3 test/webcam/nv12/restart-tu/check.py
python3 test/webcam/nv12/restart-tu/diagnostics.py build
python3 test/webcam/nv12/restart-tu/diagnostics.py run
python3 test/webcam/nv12/restart-tu/run.py
python3 test/webcam/nv12/restart-tu/run.py --confirm
python3 test/webcam/nv12/restart-tu/balanced.py
python3 test/webcam/nv12/restart-tu/scene-run.py
python3 test/webcam/nv12/restart-tu/choose-candidates.py
python3 test/webcam/nv12/restart-tu/report.py
```

Prerequisites: saved next-round support, both camera batches and multi-camera
drivers, GCC deferred archives, and restart-fast's generated initial source
and fixtures. Their builders and source patches are saved in those folders.
Generated native source/objects, changed archives and assembly remain under
/tmp/mjpeg-restart-tu. Source generation retains the upstream license header;
scan-hook patches and exact compile flags are saved here. The initial-* JSON
and native snapshots describe the earlier shared-zigzag setup; their old
binary paths are historical, not current-hash assertions.

No production src/simd changes, commits, pushes, device writes or default
selection changes were made. `manifest.json` records durable evidence and
current artifacts; camera input hashes are retained in multi-camera and the
original capture manifests.
