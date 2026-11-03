# Restart plan: fastest webcam MJPEG → NV12

## Objective and working agreement

Continue optimizing the CPU JPEG-to-NV12 path for GPU upload and H.264/H.265 encoders. Investigate structural work reduction rather than tuning exclusively for the current CPU. User intends to restart Codex with unattended writes permitted in this repository and `/tmp`.

Work autonomously on isolated, reversible experiments; save code, results and conclusions. Do not commit or push new experiments without a new request. Keep production `src/` and `simd/` unchanged during investigation. Preserve existing uncommitted experiments. Benchmark and validate JPEG → NV12 only: do not run unrelated RGB/PNG utilities or the entire CTest suite. Communicate meaningful progress periodically. Do not add quality loss without recording it separately; the next coefficient/layout and Y-IDCT changes should preserve current output exactly.

## Comparison policy — latest user instruction

- **Do not use PGO in comparisons anymore. LTO is allowed.** Rebuild complete codec archives without profile generation/use/sample flags; do not mix retained PGO-trained members into a nominally unprofiled candidate.
- Match compiler, optimization/LTO settings and CPU feature tier across baseline/candidate. Native NASM and shared non-PGO C++ support remain valid; keep their configuration consistent and preserve the established UV contract.
- Earlier PGO-assisted cohorts remain historical evidence, not current headline numbers or proof of no-PGO gains. The previous `overall/` cohort is superseded. Fresh untuned compiler comparisons live in `no-mtune/`; `lto-only/` is the preceding tuned, no-PGO reference.

## Current selection after executing phases A–D

Completed 2026-11-02. See [batch evidence](next-round/README.md),
[exact-fast kernel](paired-fast-chroma/README.md), and
[zero-group skipping](chroma-zero-groups/README.md).

- Preferred existing reduced-UV contract: `/tmp/mjpeg-chroma-zero-groups/nv12 fast 2 PASSES JPEG...`. Separate confirmation versus previous selection: Clang 3.3984 → 3.2511 ms (4.33% less time), GCC 3.5761 → 3.4366 ms (3.90%). Byte-identical to previous reduced output; its existing approximation remains.
- Separately selectable stock-fast-exact NV12: `/tmp/mjpeg-paired-fast-chroma/nv12 fast 3 PASSES JPEG...`. Against matched stock-fast decoding: Clang 4.5495 → 3.1615 ms (30.51%), GCC 4.5738 → 3.3569 ms (26.61%). Whole NV12 byte equality, independent Cb/Cr quantizers; not stock-accurate equality.
- Both confirmation cohorts improved in every bracket. Same Ryzen 9 3900X, CPU 0, 90 preloaded frames, matched no-PGO/no-explicit-tune builds with LTO. One scene remains a limitation.
- Phase A refreshed costs/counters, ablations and reproducibility; paired Y remains beneficial, while span benefit is compiler-sensitive. Phase B retained the exact-fast kernel. Phase C rejected packed entropy control words (3.21%/2.64% slower). Phase D retained exact zero-group skipping.
- Flags, modes, hashes, audits, raw rounds and validation are under `next-round/` and the individual experiment folders. Original `/tmp/mjpeg-no-mtune/` baselines remain unchanged. Source-only Clang reconstruction was executed and validated; GCC recipe is saved but unexecuted.
- Production `src/` and `simd/` remain unchanged; no commit/push. Phase E's two-MCU experiment was subsequently authorized and tested without a useful gain; broader workloads remain outstanding before new default recommendations.

## Compiler-gap follow-up

[Compiler crossover, protection controls and profiling](compiler-gap/README.md)
localize the Clang/GCC difference mainly to entropy code generation. Crossing
native entropy objects into either LTO host preserves the ordering. With
explicitly matched stack/control-flow protection, Clang entropy takes 3.1322 ms
versus GCC 3.3153 ms in the same host (5.84% extra GCC time). Original function
assembly and process counters show more GCC instructions, stack references and
speculative lookup-field loads; individual contributions are not cycle-isolated.
Existing selections remain unchanged; no mixed-compiler default is selected.

## GCC deferred-field follow-up

[Flag and source-expression experiment](gcc-deferred-loads/README.md):
`-fno-hoist-adjacent-loads` produces a byte-identical executable and is not
useful here. A pointer-based lookup expression that reads coefficient fields
after acceptance improves GCC confirmation 3.3934 → 3.2180 ms (5.17% less
time); all eight initial/confirmation brackets improve. Clang has no gain
(+0.63% confirmation), so retain its original source variant. All tested NV12
bytes and 130 coefficient streams match; LTO/default protections remain,
with no PGO or explicit CPU tuning. Separate GCC alias:
`/tmp/mjpeg-gcc-deferred-loads/nv12 fast 3 PASSES JPEG...`. Existing selections
remain unchanged. Dense synthetic timings include one retained regression;
broader-scene/CPU coverage is still outstanding. No new stock-baseline
headline was measured in this follow-up.

## Two-camera mode coverage follow-up

[Geometry-aware validation and timing](multi-camera/README.md) covers 2,148
new frames: 119 Logitech modes / 17 sizes and 60 LifeCam modes / 12 sizes.
All stock-fast-exact, GCC deferred-source, strided/padding and generic-edge
checks pass, including alternating cameras with different Huffman tables.
New 1080p comparisons: Logitech reduces stock time by 31.17% Clang / 29.43%
GCC; LifeCam by 12.95% / 14.45%. These are fresh cohorts, not replacements
for the original single-scene absolute timing numbers.

Every LifeCam frame has restart markers once per MCU row. The current entropy
controller disables its fast path for any restart-enabled scan: diagnostic
LifeCam fast calls=0, slow calls=194,400 on twelve 1080p frames. Consequently
the GCC fast-loop rewrite provides no reliable LifeCam gain, versus about
5.5–6.3% on the new Logitech modes. Do not claim universal 5% source gains.
This motivated the restart-aware fast path subsequently tested below.
Parallel restart-row decoding remains unexecuted. Preserve marker, DC,
rollback and suspension semantics; do not merely remove the current guard.

LifeCam's capture restoration returned YUYV 640x480 but 7.5 fps rather than
the original reported 5 fps; the capture summary correctly flags the mismatch.
Actual arrival rates often differ from nominal rates. Existing selections and
production sources remain unchanged; all measurements are no-PGO with LTO,
no explicit CPU tuning, on the same Ryzen 9 3900X. A second CPU and broader
scene coverage remain outstanding.

## Restart-aware entropy follow-up — completed

[Restart-aware fast path, state-safety tests and timings](restart-fast/README.md)
retains a separate candidate for restart-bearing streams. LifeCam 1080p
confirmation: Clang 5.3823 → 3.9904 ms (25.86% less time), GCC 5.4809 →
4.0532 ms (26.05%). New primary stock-fast comparisons show 34.42% / 36.35%
less time, respectively. The fast path now commits 98.77% of the LifeCam's
MCUs, versus zero previously, while retaining the final-MCU slow path and
replaying marker-lookahead attempts after per-block coefficient cleanup.

The first implementation slowed non-restart data and is not selected. One
revision chooses a separate decoder at scan startup, preserving the original
non-restart routine's source. Compiler code generation still changes: longer
Logitech confirmation costs +1.34% Clang / +0.68% GCC, and sparse DRI-3
synthetics regress 7–8%. Retain this as an explicit restart-workload option;
do not change existing defaults or advertise a universal gain. No third
tuning variant was attempted. Further refinement must address these measured
limits before a general default recommendation.

All 2,148 new camera frames, 51 restart/table/fill fixtures, 2,325 literal
coefficient streams and 127,934 forced suspension cases per compiler/harness
run pass. Both accurate and fast modes, padding, generic edge fallbacks and
alternating restart/non-restart camera state retain output. Constant retry
clears remain inline; LTO/default protections/BMI2 stay matched, with no PGO
or explicit CPU tuning. Separate mode-3 aliases and hashes are recorded in
`restart-fast/candidates.json`. Production src/simd and prior selections are
unchanged; no commit/push or row parallelism was performed.

## Restart decoder translation-unit isolation — completed

[Native restart unit and regression checks](restart-tu/README.md) supersedes
the same-TU restart candidate for investigating its non-restart penalty. The
original codec retains LTO; only the new restart unit is compiled natively to
prevent optimizer merging. Its slow helpers and standard zigzag table are
separate copies, leaving the original entropy call graph/data references alone.
Both Clang and GCC ordinary entropy instructions normalize identically to
control (1,342 / 1,647 sites). Original control executables are byte-identical
to the prior multi-camera baselines.

LifeCam 1080p confirmation retains 23.25% less time with Clang and 26.97%
with GCC. A five-bracket fixed ABBA/BAAB Logitech repeat measures -0.62% /
-0.02%, comparable to identical-binary noise (+0.64% / -0.13% means): no
repeatable Logitech regression detected. Earlier noisy cohorts are retained,
including a Clang +8.45% bracket that pushed its first confirmation to +3.29%.
Do not present instruction identity as a guarantee of identical runtime or
discard those earlier observations.

All 2,148 camera frames, 51 restart fixtures, 2,325 coefficient streams and
127,934 forced suspensions per compiler/harness pass. Short sparse intervals
still regress (roughly 6–8% on zero-AC DRI-3); Clang's DRI-1 case also remains
slower. New aliases/flags/hashes are in restart-tu/candidates.json; previous
defaults, production src/simd and prior experimental aliases remain unchanged.
No PGO, CPU tuning, commits/pushes or restart-row parallelism were added.

## Single-thread restart segments — completed

[Segment controller, exactness and confirmation](restart-segment/README.md)
keeps bit/DC state local across header-defined restart groups, reconstructs
one MCU at a time and removes per-MCU entropy dispatch. No threading or marker
prescan. Eligible selection follows scan structure; Logitech DRI-0 falls back.

LifeCam 1080p confirmation against the previous isolated restart candidate:
Clang 3.9933 → 3.8872 ms (2.66% less time); GCC 3.9299 → 3.9491 ms (0.49%
more). Same-executable toggles improve 4.27% / 3.14%, but that does not make
GCC's packaged executable faster. Retain a separate Clang alias only; prior
GCC selection and all defaults remain unchanged. Logitech Clang frozen-
reference mean is -0.10%, with mixed brackets and a retained large outlier in
the separate toggle control; GCC costs +1.37%. No universal gain is claimed.

Both compilers pass all 2,148 camera frames, 51 restart fixtures, 2,325 raw
coefficient traces and 127,934 forced suspensions per variant. Original core
archives and normalized entropy/controller instructions are unchanged. The
initial implementation and one packaging revision are saved separately.
Short synthetic results and limitations are retained in the report. This
batch is complete; no third tuning variant, production edits or new defaults.

[All-resolution follow-up](restart-segment/ALL_RESOLUTIONS.md) benchmarks all
29 camera/resolution groups with both compilers and three brackets. Clang
improves every LifeCam resolution and every bracket; GCC remains mixed.
All output hashes match. Existing selections remain unchanged.

[Current best versus stock, all cameras/resolutions](best-vs-stock/README.md)
now supplies the requested baseline comparison: all 17 Logitech and 12 LifeCam
resolutions, both compilers, with preselected exact-fast candidates and stock
fast NV12 controls. All 174 brackets improve and match output hashes. This
fresh cohort is separate from the incremental segment-versus-restart sweep.

## Partial-MCU fused reconstruction — completed

[Visible-edge reconstruction and validation](partial-mcu/README.md) adds
exact-fast fusion for even partial 4:2:2 geometry. Interior MCUs write directly;
right/bottom/corner tiles use local full-MCU reconstruction and visible copies.
All 2,148 camera frames, 133 new coefficient-domain fixtures, 57 old fixtures
and forced suspensions pass both compilers. Untimed counters verify selection.
The initial inline implementation and one out-of-line helper revision are saved.

The four affected Logitech resolutions improve in every bracket against the
previous fallback and stock. Separate partial-geometry aliases are retained;
small aligned-frame costs remain, so previous full-MCU/default selections are
unchanged. Current-best-versus-stock's earlier table remains historical; new
edge comparisons have fresh adjacent controls rather than synthesized ratios.
No production changes, threading, PGO, explicit tuning, commit or push.

## Extended plan — next optimization batch

We are not out of plausible work, but do not promise another large percentage.
The next priorities are a quality-matched fast-chroma path and work reduction
supported by new measurements. Execute the phases below in order. The current
preferred reduced-UV executable remains the control, with inline AVX2 zeroing.
This section is the active continuation; the original experiments/recovery
instructions below are historical, not instructions to restore PGO builds.

### A. Refresh the untuned, no-PGO cost map and component evidence

1. Use the validated `no-mtune/` Clang and GCC configurations: O3, compiler-
   appropriate LTO, no PGO, no explicit mtune/march/mcpu. Retain the same
   BMI2-on-entropy tier and shared native wrapper policy. Audit all codec
   members again after changing a build recipe; a clean link command alone
   is insufficient. Keep compilation/verification separate from timing.
2. Make the next baseline preparation reconstructible from repository source,
   saved patches and the actual capture. Remove dependencies on old temporary
   codec archives/generated wrappers where practical. Preserve old artifacts
   and hashes; do not silently change JPEG inputs or substitute a hot fixture
   for sequence timing. Missing capture/second-machine prerequisites must be
   reported honestly. This is a small preparation step, not a public API rewrite.
3. Re-measure entropy+coefficient construction, paired Y and reduced UV under
   the **current no-PGO** codec. Old stage numbers such as 2.46/0.36/0.63 ms
   came from a different, partly profiled configuration and are not current
   fractions. Batch-time whole passes; clearly distinguish isolated hot-output
   kernels from the real interleaved pipeline. Never add/subtract independent
   stages as exact accounting or feed stale coefficients to ordinary IDCT.
4. Use untimed counters for LUT hit/single/pair/fallback rates, refills,
   stuffing/marker retries, and chroma zero-row/half-group frequencies. If
   available without privilege changes, collect cycles, instructions and
   branch/cache statistics. These are diagnostics, not compiler profile input.
   If counters are unavailable, use timing/disassembly rather than blocking
   on perf permissions. Inspect the active decoder through the function
   pointer installed by `jinit_huff_decoder`, and the fusion-calling controller;
   do not select the first same-named private function in the executable.
5. Recheck precomputed span versus original step1+step2 in matched no-PGO/LTO
   builds. The old 1.06% source-gain claim used PGO and does not establish its
   no-PGO gain. A paired/unpaired fast-Y ablation can likewise quantify the
   current component contribution. Keep UV, zeroing, flags and other objects
   identical. Both ablations must preserve current complete NV12 bytes.

Deliver: updated stage/counter table with attribution limits, a small component
ablation table, exact build/source hashes, and the strongest next hypothesis.
Do not rerun every previously rejected experiment merely because PGO is gone.

### B. Highest-priority new kernel: fused, stock-fast-exact Cb/Cr

Hypothesis: the register-rewritten paired integer transform may be useful for
Cb/Cr as well as Y. It could avoid floating-point weighted reconstruction
while also eliminating the chroma-output difference from stock **fast** IDCT.
This is an untested alternative, not a claim that the existing reduced UV
kernel fails to process Cb/Cr together; it already does. Nor is stock-fast
IDCT equivalent to stock-accurate IDCT.

1. Add a separately selectable experimental `fast-exact-UV` mode. Adapt paired
   IFAST arithmetic to Cb/Cr, clip/round each reconstructed byte exactly as
   native fast IDCT does, then average adjacent byte rows with `(a+b+1)/2`,
   interleave Cb/Cr and write four final UV rows. Do not average transform
   values before clipping/rounding for this output contract.
2. Handle independent Cb/Cr multiplier tables explicitly. First consider a
   per-frame content-equality guard that uses shared-quantizer paired loads
   when equal and a verified ordinary fallback when unequal; alternatively
   load different multipliers into the two AVX2 lanes. Pointer equality or
   assuming table identity persists across frames is insufficient. Include
   table checks/setup in full-path timing. This is not a retry of the rejected
   expanded-Y-quantizer cache.
3. Compare every captured chroma pair and at least 10,000 synthetic pairs to
   two native fast IDCTs followed by byte averaging/interleaving. Cover equal
   and unequal tables, table replacement and in-place mutation, DC-only,
   sparse/dense/full-range signed coefficients, clipping, nonzero output
   offsets, unaligned destinations and unchanged padding.
4. Validate full **Y and UV byte equality to stock fast NV12** on all captures,
   six fixtures and mixed table-change sequences. Preserve generic/progressive,
   restart, edge/unsupported-geometry and unsupported-ISA fallback behavior;
   do not widen the prototype's supported geometry without separate validation.
5. Measure three explicit cases: stock fast NV12, current reduced-UV candidate,
   and fast-exact-UV candidate. Use matched no-PGO/untuned LTO builds for both
   compilers, identical entropy/Y/zeroing in the two candidates, and direct
   kernel plus whole-NV12 timings. Do not extrapolate isolated savings into a
   promised frame gain. Report latency and output contract together.

Keep the current preferred reduced-UV contract intact during this experiment.
Fast-exact-UV is a separate quality/performance option, not a silent replacement.
Even a similar-speed result could be useful as a byte-exact stock-fast option;
it must not be called a stock-accurate decoder. Save it under a new experiment
folder, for example `paired-fast-chroma/`.

### C. Focused entropy changes, selected from phase A evidence

The reservoir → LUT index → consumed-bit count → next index dependency remains
serial. Avoid a broad collection of unrolling/lookahead variants. Choose ONE
of the following first, based on the new active assembly and counters:

- **Current-entry control metadata layout.** Put consumed-bit count and total
  span adjacent/in one small control word so the successful-hit guard can
  potentially use one load, while leaving coefficient payload late. Keep
  eight-byte entries and the same lookahead width. Verify the compiler does
  not already combine these loads. Extra shifts/masks or live registers can
  erase the benefit. This differs from the rejected full-next-entry packed
  prefetch; do not resurrect that larger live-state experiment without evidence.
- **Outline only rare refill work.** If counters show byte-stuffing/marker
  handling is rare and inspection suggests excessive hot-code size/spills,
  keep the clean bulk refill inline and test a cold helper for the exceptional
  path. Measure the call/state-transfer cost and instruction footprint; source
  size reduction alone is not a win. Do not change bit order, refill budget,
  bounds checks, state commit, marker reporting or rollback semantics.

Each change needs a matched source control with the same whole-codec no-PGO/
LTO recipe, plus Clang/GCC assembly inspection. Compare every coefficient
literally before IDCT, full-frame output, all six fixtures and table changes.
For refill changes, add a boundary/source fixture that actually exercises a
fast-decode marker retry and prove it with untimed counters. A restart-interval
fixture alone is insufficient: the current decoder disables its fast path
when restarts are enabled. Valid trailing-data/EOI and source-chunk boundaries
may help construct a targeted case; verify the path rather than assume it.
Keep any malformed-input observations distinct from valid-input performance.

Stop the branch if added register pressure, rare-path transfer or code size
costs more than it saves. No PGO retraining or CPU scheduling flags to rescue
an unsuccessful source change.

### D. Preserve reduced-UV bytes while skipping zero contributions

The existing reduced kernel evaluates vertical contributions even when the
corresponding quantized coefficient group is entirely zero. Count this first
across the full capture and varied inputs; sparsity of one frame is not enough.

1. Inspect scheduling, coefficient conversion, matrix loads and spills in the
   actual shared native wrapper. Eliminate redundant work only when present;
   the compiler may already fold loads into FMA operands.
2. If zero-group frequencies justify a trial, test a narrowly scoped check
   that skips a contribution only when **all relevant Cb/Cr lanes are zero**.
   Reuse already-loaded integer coefficients where possible; count additional
   scans/loads/branches. Start with the most promising row/half group rather
   than adding checks to every frequency or scanning whole blocks blindly.
3. Preserve the order of every nonzero FMA and the current rounding/clipping.
   This is exact-zero work elimination, not dropping high-frequency terms.
   Validate complete current NV12 bytes, changed quantizers, clipping-heavy
   synthetic pairs and padding. If reassociation/factorization changes bytes,
   classify it as a separate quality variant and keep it out of this contract.
4. Benchmark dense/noisy and sparse inputs as well as the original capture.
   Stop if checking overhead or misprediction erases the gain. Do not infer
   new sparse-scene behavior from the old Y zero-column counts.

### E. Conditional scheduling and broader workloads

Subsequently executed on user request: [two-MCU report](two-mcu/README.md).
Buffering-only means changed +0.56% Clang / +0.48% GCC; a shared-dispatch
revision changed +0.78% / +0.72%. Positive means slower; these small changes
overlap noise. Neither variant establishes a gain, so both are parked and the
previous selections remain. Byte-exact output, padded destinations, forced
input suspension, odd/one-MCU rows, restart and progressive fallback tests
passed on both compilers. No PGO or explicit CPU tuning; LTO retained.
One focused revision was tried; do not reopen this branch without new evidence.
The broader-real-workload and second-CPU work below remains outstanding.

Only if the new cost map identifies meaningful controller/scheduling overhead,
try one strip-level fusion dispatch or a two-MCU reusable buffer. Preserve
suspension/rollback, row/edge accounting, output order, table changes and generic
fallbacks. Measure extra footprint and calls removed. Batching calls does not
itself prove overlap between serial entropy and reconstruction; inspect actual
scheduling. Do not pursue this ahead of the simpler kernel/source trials.

Before recommending new defaults, test varied **real** MJPEG scenes/qualities
and, if available, a second CPU. Sparse/dense synthetic fixtures test boundaries
but are not substitutes for real-scene coverage. Test supported edge dimensions
and 4:2:0 fallback separately from the optimized full-MCU 4:2:2 path; the current
hardcoded sequence driver needs deliberate geometry support before claiming
those workloads. Missing scenes/hardware are limits, not a reason to invent
results. GPU upload/encoder integration remains a later, separately scoped
measurement; CPU decode savings are not end-to-end encoder throughput gains.

### Gates, stop rules and reporting

- Preserve the two explicit output contracts: current reduced-UV bytes versus
  stock-fast-exact NV12. The existing 25.0% headline includes approximate UV;
  label it accordingly. Any new quality-matched claim requires the entire
  fast-exact-UV output to match stock, not just luma or an aggregate error mean.
- Keep inline AVX2 zeroing as requested; do not reopen libc-versus-inline choice
  or add sparse-reset complexity without a new instruction/evidence.
- Benchmark CPU 0 with preloaded inputs, warmup, matched flags/feature tiers,
  bracketed or balanced controls and an identical-binary noise control for
  small effects. Rotate order and save all rounds. Do not lock/change machine
  settings or assume a second host is available. Repeat promising effects in
  a separate cohort; call unresolved effects inconclusive rather than wins.
- Start with one implementation per hypothesis and at most one alternative
  when evidence explains a failure. Park a branch after two unhelpful variants
  unless new measurements change the hypothesis. Do not stack losing changes.
- Accept a code optimization on sustained whole-NV12 benefit, exact target
  output and manageable complexity. Report both compilers and any regression;
  one compiler/scene win is not a universal source improvement. Keep accurate
  IDCT behavior unchanged wherever the new fast-only kernel does not apply.
- Save patches/source, reproducible scripts, compile/archive audits, literal
  coefficient checks where relevant, complete validation and raw compact JSON
  under new experiment folders. Leave binaries/traces under `/tmp`. No commit,
  push or production `src/`/`simd/` changes are authorized.

Phases A–D below are now completed; their hypotheses and gates are retained
for the evidence record. If those branches produce no stable gain, stop tuning
this capture and prioritize real-workload/second-CPU evidence or packaging.

## Historical state at restart

- Repository: `/home/al/src/libjpeg-turbo`; branch `albert/experiments`.
- Latest commit, already pushed: `6cc4db29`, paired AVX2 Y-block IDCT experiment. Previous base: `d7a7af9e`.
- Uncommitted work: `test/webcam/README.md` links plus `nv12/lut-pipeline/`, `nv12/mcu-specialization/`, `nv12/stock-fast/`. Do not discard or accidentally include these in another commit.
- CPU: AMD Ryzen 9 3900X (Zen 2), CPU 0 used for timing. GCC 13.3, Clang 18.1, NASM. Frequency not fixed; retain noisy observations and use paired comparisons.
- Input: `test/webcam/20261023T230418Z/frame_*.jpg`, 120 frames, 1920×1080 4:2:2. First 30 were profile training; last 90 held out for performance measurement. They are one scene, not broad workload coverage.
- 16,200 MCUs/frame, each two Y blocks, one Cb block and one Cr block; no DRI/RST in original capture.
- Current candidate: scalar bulk reader + cached 10-bit two-AC-symbol LUT + pre-shifted long-code thresholds, retained Clang PGO/ThinLTO codec, fused reduced chroma, paired fast Y IDCT.
- Current end-to-end paired-Y result: confirmation control 3.6417 ms → paired 3.5576 ms (−2.31%). Initial batch: 3.6611 → 3.5775 ms (−2.28%). Each five-bracket batch had one regressing round; report this variability.
- Paired Y arithmetic is byte-exact to existing IFAST; reduced chroma has a previously measured approximation versus accurate chroma. Preserve that same output contract, not a newly implied stock-accurate equivalence.

## Historical recovery notes — not current build instructions

For historical context only; the active baseline is `no-mtune/`, and its build/audit/validation scripts supersede the commands below. Earlier source files remain useful references, but do not link their retained PGO archives.

Original reading list:

- `paired-idct/README.md`: current Y kernel, build and timings.
- `fused-chroma/README.md`: controller hook, exact and reduced UV paths.
- `stages/README.md`, `chroma-budget/README.md`: older stage estimates and measurement limitations.
- `lut-pipeline/README.md`, `mcu-specialization/README.md`: recently rejected/limited candidates.

Useful retained artifacts (check existence; `/tmp` is not durable):

| Path | Role |
|---|---|
| `/tmp/mjpeg-paired-idct/{control,paired}` | Matched current full NV12 binaries |
| `/tmp/mjpeg-paired-idct/{control.cc,paired.cc,pair.o,check}` | Generated wrappers, paired assembly object, direct kernel verifier |
| `/tmp/mjpeg-fused-chroma/pgo/{libjpeg.a,libturbojpeg.a}` | Fused-controller codec archives, otherwise retained Clang PGO/ThinLTO |
| `/tmp/mjpeg-fused-chroma/{driver.o,fusion.o,exact.o}` | Shared NV12 driver and chroma kernels |
| `/tmp/mjpeg-fused-chroma/source` | Isolated codec tree containing raw MCU controller hook |
| `/tmp/mjpeg-stb-src/threshold-pair10` | Best entropy source prototype |
| `/tmp/mjpeg-pgo-lto` | GCC/Clang baselines, profile builds, common sequence and embedded-frame objects |
| `/tmp/mjpeg-google-bench` | Google Benchmark headers/archive |
| `/tmp/mjpeg-lut-pipeline/fixtures` | Six 1920×1080 4:2:2 boundary JPEG fixtures |

Build metadata is in `test/webcam/bmi-intrinsics/pgo-lto/build-summary.json` and individual experiment JSON files. If artifacts are missing, reconstruct from scripts and report missing capture/profile prerequisites honestly; do not silently substitute another image or pipeline.

Existing commands:

```sh
python3 test/webcam/nv12/paired-idct/build.py
taskset -c 0 /tmp/mjpeg-paired-idct/check
python3 test/webcam/nv12/paired-idct/run.py
# Timing-only repeat, if new changes or unresolved variability justify it:
python3 test/webcam/nv12/paired-idct/run.py --timing-only
```

`build.py` regenerates assembly from upstream SSE2 IFAST and matched wrapper objects; it does not rebuild the entire codec. `run.py` validates capture and fixtures, then measures CPU-0 control/candidate/control brackets with preloaded files. Do not overwrite old results when testing a new candidate: use a new experiment directory/output names.

## Original experiment 1 — completed, historical methodology

Start here. Old stage figures (~2.69 ms for entropy including coefficient clearing/stores, ~0.63 ms Y IDCT) predate the current codec/kernel combination. Do not present them as current fractions or subtract independently measured stages as exact accounting.

1. Inspect the current controller's MCU-buffer clear and the entropy decoder's DC/AC/zigzag stores. Determine exactly which bytes are cleared and which are then overwritten. Inspect optimized assembly, including whether the clear is already vectorized/inlined.
2. Create a diagnostic build to count cleared bytes, nonzero coefficients, touched coefficient cache lines, and block sparsity across all 120 frames. Collect counters outside timed builds. Count real behavior instead of assuming coefficient clearing is expensive.
3. Measure whole-stage entropy plus construction with the current source, using batch timings rather than clocks around every MCU or symbol. Measure the current paired Y and reduced UV kernels separately as context. Label isolated kernels and in-pipeline timings clearly.
4. Estimate clearing/store cost with a controlled microbenchmark over real coefficient traces and the actual reusable MCU-sized working set. An entropy sink/no-store diagnostic may bound potential, but changes its dependency/memory behavior and must not be treated as an exact subtraction. Never feed uncleared stale coefficients to ordinary IDCT for a purported valid speed result.
5. Use the results to decide whether to pursue clearing, layout, or entropy arithmetic. If clearing is tiny, stop that branch rather than implementing a complicated sparse reset.

Deliver a stage/counter table, a stated uncertainty for each attribution, and one selected implementation experiment.

## Original experiment 2 — screened and stopped

Hypothesis: writing coefficients in the layout consumed by the paired transform can remove repeated packing, but address computation in serial entropy decode may outweigh that saving.

1. Keep the existing representation/control. Consider a 32-byte Y row containing eight coefficients from Y0 and eight from Y1, matching independent AVX2 lanes. Cb/Cr can remain ordinary blocks.
2. First test an explicit post-entropy layout conversion plus a paired kernel using direct 32-byte loads. This provides a conservative full-path result, not proof that direct emission helps.
3. If promising, prototype direct Y emission in a guarded specialized path. The decoder currently indexes 64-element blocks through JPEG natural-order tables; a row-interleaved pair cannot be represented merely by changing two block pointers. Explicitly adapt stores and IDCT consumption, retain generic fallback, and avoid out-of-bounds block assumptions.
4. Validate every coefficient against ordinary decoding before testing output. Preserve entropy rollback/slow-path behavior: if the specialized fast decoder encounters a marker and retries, fallback coefficients must still reach the selected IDCT in the correct layout. Define fallback conversion/dispatch deliberately.
5. Benchmark complete NV12 against the existing paired-Y path, not against the older unpaired control. Record added entropy cost separately from packing savings. Check generated code under GCC and Clang for compiler-sensitive address/spill regressions.

This is a hypothesis, not an already established win. Reject it if extra entropy complexity costs more than it saves.

## Original experiment 3 — register rewrite retained; quantizer cache not selected

Potentially lower-risk alternative if layout changes disappoint:

- The current assembly is mechanically widened SSE2, with copied two-operand scheduling followed by three-operand AVX2 instructions. Inspect opportunities to remove redundant copies and stack temporaries while preserving exact arithmetic.
- Test pre-expanded quantizer rows cached per quantization table versus per-call broadcasts. Include setup/cache footprint and table-change validation; quantizer caching must not assume all future frames have unchanged tables.
- Sparse shortcuts are optional candidates, not automatic improvements. In embedded frame 60, only 141/16,200 Y pairs have both blocks eligible for the upstream zero-column shortcut; 597 have exactly one eligible block. Measure sparse scenes as well as the original capture before adding checks.
- Benchmark direct kernels and complete NV12; the previous direct kernel gain (~40 → 22 ns/pair) translated to only ~84 µs/frame end-to-end. Do not multiply isolated savings into a promised pipeline speedup.

## Original later candidates — consult active extension before execution

- A two-MCU, single-thread coefficient buffer may expose overlap between independent reconstruction and subsequent entropy work. Calls do not automatically overlap: inspect actual scheduling, footprint and buffering cost. Try only after current costs identify a credible opportunity.
- Pairing exact Cb/Cr transforms targets the accurate path. The fastest reduced-chroma kernel already processes Cb and Cr together; do not claim this is a new optimization for that path.
- A second CPU (ideally Intel or another AMD generation) and varied real scenes are needed before recommending new defaults. No second machine is currently established as available.
- Plain Huffman/MCU unrolling, wider lookahead, blanket cache alignment and early copying of full next-LUT entries are low priority: earlier experiments were neutral/slower or increased register pressure. Minimal next-entry metadata gave ~1% only for the accurate-luma profiled path, with no fast-luma win.
- Historical profile-derived findings are hypotheses only. Current policy forbids PGO in comparisons: use fully unprofiled archives and matched LTO; do not retrain PGO to rescue a changed loop.

## Historical validation checklist — active extension and latest policy take precedence

- Preserve current NV12 bytes for this work: all 120 captures, both accurate and fast IDCT where applicable, plus six fixtures (`rst1`, `optimized`, `progressive`, `dense`, `tail63`, `zeroac`). Check padded/unaligned destinations and unchanged padding.
- Coefficient layout changes require coefficient-level equality and careful fast/slow fallback checks, not only a final-MCU hash. Use full frame output hashes and meaningful boundary cases.
- Direct IDCT changes retain captured-pair checks and 10,000 synthetic pairs, including sparse and full-range signed coefficients.
- All timing inputs loaded before measurement; allocation, output hashing and diagnostics outside timed regions. CPU 0, warmup, rotated or bracketed controls, raw rounds saved. Run benchmark processes sequentially; do not compile or run another CPU-heavy verifier concurrently.
- Prefer sustained end-to-end improvements with unchanged output and manageable code size. Report regressions, noisy rounds, workload specificity and changed objects. Stop branches that fail rather than layering optimizations indiscriminately.
- Save reviewable patches/source, reproducible scripts, compact JSON evidence and a concise conclusion under a new `test/webcam/nv12/` experiment folder. Keep generated binaries/profiles/large traces in `/tmp` or ignored outputs.

## Sandbox note for restart

The installed CLI supports:

```sh
codex -C /home/al/src/libjpeg-turbo \
  --sandbox workspace-write --add-dir /tmp --ask-for-approval never
```

In the previous session sandboxed shell calls failed with `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`, so shell work required escalation. `never` disables approval requests but does not repair the sandbox. If this persists after restart, explain the execution blocker; do not silently switch to unrestricted filesystem access. Reading the saved plan is the restart entry point, not an instruction to commit/push or bypass sandbox policy.
