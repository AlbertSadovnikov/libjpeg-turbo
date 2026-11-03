# Current coefficient costs and paired Y layout/register experiments

> Historical PGO-assisted cohort. The user now requires no PGO in comparisons,
> with LTO allowed. Use [the matched LTO-only report](../lto-only/README.md) for
> current overall numbers and selection; the original evidence below is preserved.

Continuation of `../NEXT_EXPERIMENTS.md`, on the Ryzen 9 3900X, CPU 0.
The production codec and SIMD trees are unchanged. All comparisons use the
retained scalar bulk reader, cached two-symbol 10-bit LUT, shifted thresholds,
Clang PGO/ThinLTO codec archives, reduced fused UV and existing paired fast Y
baseline. This preserves the existing approximate-chroma contract; it is not
new equivalence to stock accurate JPEG output.


**Result:** retain the register-only paired-Y rewrite: initial whole-NV12
latency improves 1.16%; a separate confirmation improves 1.00%, with all ten
brackets improving. Reject explicit post-entropy layout conversion (+2.19%)
and stop sparse-reset work (hot-buffer clearing about 0.071 ms/frame).
Output remains byte-identical to the current candidate on targeted validation.
These are one-scene, one-CPU results; no production default changes.

## Coefficient construction

The controller calls `jzero_far(MCU_buffer[0], blocks_in_MCU * sizeof(JBLOCK))`
before each MCU. For these captures that is 512 bytes (four 128-byte blocks).
It clears every DC and AC slot, including values immediately overwritten by
entropy decoding. **Audit correction:** the active fused controller's ThinLTO
code already calls libc `memset` directly. The initial audit inspected the
other same-named private controller from the second codec archive, which
calls `jzero_far`; that function tail-calls libc `memset`. `audit.py` now selects
the controller that calls the fusion dispatcher. The microbenchmark explicitly
calls `jzero_far`, so its recorded timings remain valid, but the active full
pipeline does not have that extra tail jump. The local libc
IFUNC resolution exposes AVX2 broadcasts and vector stores. `audit.py` records
its bytes and file offset without tracing a benchmark process. The exact
implementation in a timed process was not observed with ptrace (disallowed
by the sandbox), but the diagnostic uses the same host/environment.

DC prediction writes coefficient 0 even when it is zero. Nonzero AC values
are scattered through `jpeg_natural_order`. The fused LUT writes twice per
hit; a single-symbol hit repeats its store. Slow fallback retains ordinary
DC/zigzag stores. No separate construction pass exists after Huffman decode.

`probe count` inspects actual controller MCU buffers, outside any timing, for
all 120 frames. Every coefficient is compared against a separate ordinary
`jpeg_read_coefficients` decode. Counts below describe final coefficient
contents and unique required store locations, **not executed store counts**:
duplicate LUT stores and speculative/rollback store events are not counted.
Their exact dynamic cost remains unattributed. The capture has no restarts.

| Counter, all 120 captures | Result |
|---|---:|
| MCUs | 1,944,000 |
| Cleared bytes (logical writes, reused buffer) | 995,328,000 |
| Final nonzero coefficients | 59,880,161 (12.032% of slots) |
| Unique DC + nonzero AC store locations | 59,906,913 |
| Unique overwritten bytes | 119,813,826 (61.633/MCU) |
| Physical cache lines intersected by each clear | 9 |
| Mean lines containing nonzero coefficients/MCU | 6.127 |
| Mean lines containing required stores/MCU | 6.131 |

The buffer starts at offset 32 within a 64-byte line in this run. Per-block
line counts can share physical lines, so use the MCU masks for unique totals.
The roughly 995 MB cleared is repeated L1 work, not 995 MB of DRAM traffic.
A required store includes zero-valued DC; an AC coefficient is nonzero.

| Component | Blocks | Mean nonzero AC/block | DC-only blocks |
|---|---:|---:|---:|
| Y | 3,888,000 | 10.8841 | 1.462% |
| Cb | 1,944,000 | 2.4832 | 17.668% |
| Cr | 1,944,000 | 2.5649 | 22.145% |

`counters.json` retains all 64-bin AC sparsity histograms and alignment counts.
It counts normal valid-input behavior, not malformed JPEG behavior.

## Current stage context

All inputs are preloaded. No clocks occur around MCUs or symbols. Stage
estimates **are not additive** and must not be subtracted from full NV12 to
claim exact reconstruction/setup accounting.

| Measurement | Mean ms/frame | Observed range ms/frame | Attribution and uncertainty |
|---|---:|---:|---|
| Full current JPEG → NV12 | 3.5410 | 3.5178–3.5999 | 90 held-out frames; 6 full-process means, each 3 passes after warmup; includes setup/finish |
| Entropy + zeroing/stores + raw controller | 2.4595 | 2.4194–2.4883 | Same codec archives/controller; 15 full-pass means over held-out frames, reconstruction dispatcher replaced with no-op; setup/finish outside clocks; changed cache/dependency behavior |
| Paired Y, isolated trace | 0.3602 | 0.3573–0.3654 | Frame 60, all 16,200 pairs, reused destination; excludes quantizer setup and normal output traversal |
| Reduced UV, isolated trace | 0.6252 | 0.6076–0.6421 | Same frame, cached real quantizer weights, reused destination; excludes setup and normal output traversal |
| 512-byte clear, reused actual buffer alignment | 0.0710 | 0.0690–0.0908 | Calls same `jzero_far`, compiler barrier after each clear; includes loop/call overhead; not in-pipeline marginal cost |
| Clear + sparse store replay | 0.3769 | 0.3747–0.3836 | Real DC/nonzero AC trace in zigzag order, one reused MCU buffer; precomputed offsets omit entropy dependencies and duplicate LUT stores |
| Store replay, no clear | 0.3183 | 0.3128–0.3257 | Diagnostic only; never supplied to IDCT or presented as valid decoded output |

Kernel/replay figures are normalized by 16,200 MCUs, from 15 batch means,
three processes with five rotated rounds. Each operation runs >=0.2 s after
warmup. `stages.json` saves every raw round. Frequency is not fixed. Ranges
are observations, not statistical confidence intervals or universal bounds.
The replay difference (~0.059 ms/frame) is a controlled microbenchmark contrast,
not exact entropy attribution. Sparse replay streams precomputed records,
whereas entropy has serial bit/DC/address dependencies and different stores.

**Decision at the stage screen:** stop sparse-reset work. The measured hot-buffer clear
cost is small, already vectorized, and sparse reset would add address/control
work. Current entropy remains the dominant isolated stage; that does not
establish an unmeasured entropy optimization. Select the simpler paired-Y
register scheduling experiment, with a conservative layout screen alongside it.

The follow-up `../memset-call/` separately tests call removal and fixed-size
inline clears. Stopping sparse reset here did not measure or rule out those
alternatives. It also corrects the inactive-controller assembly attribution.

One exploratory cohort is retained as `rejected-uv-setup-*`: the initial UV
setup passed a small scratch pitch, failed its geometry guard, and went
unchecked. Its UV weights were invalid for timing real reconstruction. The
final probe uses full-width pitch and requires setup success; final tables
use regenerated data only.

## Explicit layout conversion

`layout.asm` replaces each pair of 128-bit coefficient loads plus insertion
with a direct 256-bit load. The matched wrapper explicitly builds eight
32-byte rows, each containing Y0's row followed by Y1's row, after entropy.
It includes the entire conversion and temporary buffer in pipeline timing.
Cb/Cr, entropy stores, generic fallbacks and rollback are untouched. Both
GCC and Clang versions retain the existing accurate-IDCT dispatch.

This conservative screen does not show what direct entropy emission would
cost. It provides no reason to introduce specialized entropy addressing or
fallback conversion unless its complete-path result is promising. Layout
conversion is verified coefficient-by-coefficient in the untimed direct
checker before checking output. No diagnostic comparisons occur inside the
timed conversion helper.

## Register scheduling

`variants.py` treats copies and the two stack slots as aliases, gives each
arithmetic result an SSA value, and assigns physical vector registers by
last use. It retains arithmetic order, all shifts/multiplications/wraparound,
coefficient and quantizer loads, and sample stores. It uses at most 10 live
vector registers, eliminating 64 vector copy/stack instructions and all
20 stack-memory operand sites. No cached quantizers or sparse shortcuts are
introduced. Quantization is still loaded afresh from the selected IDCT table.

The assembly shrinks from 268 instructions / 1,222 text bytes to 198 / 922,
including removal of the stack prologue/epilogue. Whole wrapper `.text` is
byte-identical between control and register variant for each compiler; the
call relocation selects the new assembly symbol. GCC's layout dispatcher
grows from 569 to 789 bytes; Clang's grows from 571 to 829. Stack-operand sites
are static assembly observations, not dynamic spill-cost measurements.

## Complete-path screening result

| Fast Y + reduced UV, matched bracket | Existing paired control | Candidate | Change |
|---|---:|---:|---:|
| Explicit row layout conversion | 3.4454 ms | 3.5210 ms | +2.19% |
| Register scheduling, initial cohort | 3.4317 ms | 3.3919 ms | −1.16% |
| Register scheduling, confirmation | 3.4087 ms | 3.3745 ms | −1.00% |

Five control/candidate/control brackets per variant, alternating candidate
order by round, 90 preloaded held-out frames, three passes after a complete
warmup. Layout regresses in all five brackets (+0.99% to +4.19%). Stop this
branch: **no direct entropy emission was implemented**. Its added entropy
cost is therefore zero in this screen; conversion work is entirely after
entropy. This does not disprove every possible direct-emission design, but
its complexity is not justified by this result.

Register scheduling improves all five initial brackets (−0.27% to −1.89%).
The effect-size spread and drift in controls prompted a separate confirmation
cohort: all five improve again (−0.69% to −1.50%), averaging a 34-microsecond
whole-frame reduction. Retain this candidate. Do not infer a fixed universal
percentage or portability to another scene/CPU from these observations.

Direct kernel means (five rounds over all captured frame-60 pairs): two SSE2
calls 39.58 ns/pair, existing paired 22.14, explicit conversion plus direct
layout 25.84, register rewrite 19.93. The conversion is included in its timing;
preconverted direct-load-only speed was not measured. The register reduction
is about 10.0% in this isolated test and about 40 microseconds/frame in the
initial whole-path brackets. These measurements have different working sets;
do not multiply the isolated gain into a promised pipeline saving.

Clang's complete wrapper **control** fails the current byte contract in
reduced-UV mode: a few floating-point sample-rounding outcomes differ from
the retained GCC wrapper. Disabling implicit FP contraction did not resolve
it. Accurate/exact mode and all Y bytes match, but that is insufficient for
acceptance. `compiler-contract.json` retains full capture hashes and error
statistics. Clang assembly is audited for layout addressing/stack effects,
but its full wrapper is excluded from timing and acceptance. No floating-point
flags were changed in the admitted GCC comparison; no changed-output result
is silently pooled with it.

All admitted variants match current complete NV12 reports on 120 capture
frames and six boundary fixtures (`rst1`, `optimized`, `progressive`, `dense`,
`tail63`, `zeroac`), both accurate and fast IDCT methods. Validation includes
unaligned/padded output strides and unchanged padding. The progressive and
restart cases exercise unchanged generic/slow fallbacks. Neither new kernel
changes entropy addressing or rollback. The direct checker also compares
16,200 captured pairs and 10,000 synthetic pairs to two upstream SSE2 calls,
including sparse/full-range signed coefficients, padding, and 10,000 changed
multiplier tables. Coefficient conversion checks are outside timing. The
counter probe separately checks all 497,664,000 captured coefficients against
ordinary coefficient decoding. This is targeted valid-input coverage, not
an exhaustive malformed-JPEG proof.

## Validation and reproduction

`build.py` links the probe against unchanged retained codec archives and
compiles the existing reduced-UV wrapper with only its unused reconstruction
dispatcher renamed. `variants.py` generates both kernels, both compiler
wrappers, reviewable patches, matched binaries and the direct checker.
`audit.py` records code sizes, wrapper text equality and the clear implementation.

```
python3 test/webcam/nv12/coefficient-cost/build.py
python3 test/webcam/nv12/coefficient-cost/variants.py
python3 test/webcam/nv12/coefficient-cost/audit.py
python3 test/webcam/nv12/coefficient-cost/run.py
python3 test/webcam/nv12/coefficient-cost/run_variants.py
# Separate confirmation, when needed to resolve initial variability:
python3 test/webcam/nv12/coefficient-cost/confirm.py
```

Run sequentially; do not compile or run another CPU-heavy process during
measurement. Dependencies are the retained `/tmp/mjpeg-paired-idct`,
`/tmp/mjpeg-fused-chroma`, `/tmp/mjpeg-pgo-lto`, `/tmp/mjpeg-google-bench`,
`/tmp/mjpeg-lut-pipeline/fixtures` and original 120-frame capture listed in the
restart plan. Generated binaries, traces and full disassembly stay in
`/tmp/mjpeg-coefficient-cost`; compact evidence and sources stay here.
No profiles are retrained or changed: the codec/entropy CFG is unchanged,
and the wrapper and new kernels are matched ordinary O3 objects without PGO.
No commit or push is made.
