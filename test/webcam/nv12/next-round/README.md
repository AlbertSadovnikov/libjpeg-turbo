# Next batch: untuned, no-PGO stage refresh and component ablations

Phases A–D of the extended plan use O3, compiler-appropriate LTO, no PGO and
no explicit mtune/march/mcpu. Existing BMI2-on-entropy, inline AVX2 zeroing,
register-rewritten Y and reduced-UV output are retained in the control.
Production sources and prior experiments are unchanged.

## Source recovery and build integrity

`prepare.py` reconstructs the prototype source from repository tracked files
plus `lto-only/codec.patch`, and reconstructs the wrapper from the repository's
fusion source. It verifies the hashes of complete no-PGO `no-mtune/` codecs
and native support before reuse. `common.py` replaces only `jdhuff.c.o` for
entropy experiments and checks every other archive member literally unchanged.
No retained PGO archive is linked. Counter instrumentation is a separate
untimed diagnostic build, never a compiler-training profile or timed candidate.

`rebuild-baseline.py` is an independent recovery route: tracked repository
source + saved patch + actual captured frame bytes, full no-PGO/LTO codec
rebuild, fresh wrapper/driver/NASM. It removes benchmark registration and the
unused old main from the application prototype, so it needs no generated
/tmp wrapper, old archive/object, or Google Benchmark dependency. The Clang
standalone rebuild matches all 120 complete output reports. This compact
application changes binary layout and has no timing claim; future experiments
using it must measure fresh matched controls. The GCC recipe is provided but
was not separately executed in this batch.

```
python3 test/webcam/nv12/next-round/prepare.py
python3 test/webcam/nv12/next-round/build-a.py
python3 test/webcam/nv12/next-round/run-a.py
# Independent source-only recovery, without retained /tmp support:
python3 test/webcam/nv12/next-round/rebuild-baseline.py --compiler clang
```

## Current stage context

| Operation | Clang codec | GCC codec | Scope |
|---|---:|---:|---|
| Entropy + coefficient clear/stores + raw controller | 2.501 ms | 2.711 ms | 90 preloaded frames, full-frame body clocks; start/finish outside |
| Paired Y | 0.356 ms | 0.323 ms | Isolated frame-60 trace, hot reused output, 16,200 pairs |
| Reduced UV | 0.645 ms | 0.618 ms | Isolated frame-60 trace, real cached quantizers, hot reused output |

The Y and UV objects are identical across codec compilers. Their observed
variation is not a compiler-generated kernel speed difference. Five stage
rounds include outliers; see `phase-a-stages.json`. These measurements are
**not additive** and must not be subtracted from full NV12 as exact accounting.
The entropy probe deliberately substitutes a no-op reconstruction hook; it
parses/constructs coefficients but is not valid reconstructed NV12 output.
All diagnostic scans and trace capture occur outside clocks.

Optional `perf stat` counters are available on this host. The retained smoke
record includes startup, loading, warmup and hashing, so it is process context,
not per-MCU attribution. No privileged settings were changed.

## Untimed behavior, all 120 capture frames

Both compiler builds produce identical diagnostic counts:

| Counter | Count |
|---|---:|
| Total MCUs | 1,944,000 |
| Fast MCU decodes | 1,926,329 |
| Slow MCU decodes | 17,671 |
| Fused single hits | 18,208,644 |
| Fused pair hits | 15,982,201 |
| LUT fallback symbols | 9,410,357 |
| Actual fast reservoir refills | 7,282,202 |
| Clean bulk refills | 7,096,500 |
| Refills whose wide FF guard fires | 185,702 |
| Stuffed FF observations | 141,727 |
| Fast marker retries in this capture | 0 |

The wide guard observes eight bytes while consuming six; a guard hit is not
necessarily an FF consumed in that refill. Fallback-symbol count includes EOB,
ZRL and long-code/amplitude cases, not just failed nonzero-pair opportunities.
The capture has no restart markers. No claim is made that it exercises retry.

Across actual paired Cb/Cr half-row groups, all v5–v7 coefficients are zero
in about 99.3% of lower halves and essentially all upper halves. Dense synthetic
fixtures have no such zero groups; zero-AC fixtures have all groups zero.
These counts motivated `../chroma-zero-groups/`; they are not real-scene
coverage beyond this one capture. Full v0–v7 half histograms and dense/sparse
counts are retained in `phase-a-counters.json`.

## Current no-PGO ablations

Positive changes mean slower when removing the selected component:

| Change from current control | Clang latency change | GCC latency change |
|---|---:|---:|
| Remove precomputed span | +1.51% | −2.66% |
| Replace paired Y with ordinary two fast-IDCT calls | +7.91% | +8.81% |
| Same-binary repeat, noise control | −0.82% | −0.37% |

Three control/variant/control brackets per case/compiler, 90 preloaded frames,
three passes after warmup, CPU 0; order rotates. All ablations preserve complete
current output on all captures and six fixtures, both IDCT modes and padding.
The same-binary Clang brackets range −1.86% to +0.83%. Do not quote the small
span result with false precision or as a universal compiler-independent win.
GCC's consistent span-off improvement is a compiler-specific finding worth
retaining; this batch does not introduce compiler-conditional source defaults.
Paired-Y removal consistently regresses both. These ablations are not additive
with each other or with earlier cohorts.

## Remaining phases and evidence

- `../paired-fast-chroma/`: separate full stock-fast-exact UV mode, independent
  quantizers per lane; current reduced contract remains available.
- `../entropy-control-word/`: one adjacent consumed-bit/span control-word
  experiment; coefficient equality passes but timing regresses, rejected.
- `../chroma-zero-groups/`: skip only provably zero high-frequency contributions
  while preserving every current reduced-UV byte.

`run-cd.py` stores shared full validation/timing records; `confirm.py` provides
a separate longer confirmation cohort. New benchmark processes, compilation
and coefficient verification run sequentially. `audit.py` checks changed codec
members for PGO metadata/flags and retains active decoder/wrapper disassembly.
All raw rounds, including noisy ones, are preserved. No commit or push.

## Final decisions and separate confirmation

A–D are complete. Retain zero-group skipping for the previous reduced-UV
contract; expose paired stock-fast-exact chroma separately. Reject packed
entropy control words (Clang +3.21%, GCC +2.64% time). Do not stack that change.
The span ablation remains compiler-sensitive, with no universal speedup claim.

Previous reduced contract versus zero skipping:

| Compiler | Control | Candidate | Time reduction |
|---|---:|---:|---:|
| clang | 3.3984 ms | 3.2511 ms | 4.33% |
| gcc | 3.5761 ms | 3.4366 ms | 3.90% |

Public stock-fast versus paired exact chroma:

| Compiler | Control | Candidate | Time reduction |
|---|---:|---:|---:|
| clang | 4.5495 ms | 3.1615 ms | 30.51% |
| gcc | 4.5738 ms | 3.3569 ms | 26.61% |

These are separate three-bracket confirmation cohorts with six passes and
rotated compiler/comparison order; every bracket improves. They must not be
combined into a single output-quality claim. `confirm-results.json` saves all
rounds; `choose-candidates.py` makes distinct aliases and `selections.json`
records explicit modes/hashes. Existing baseline aliases remain available.

`audit.py` verified changed archive members for absent profile flags/metadata,
checked reused archive hashes, and retained active Clang entropy and native UV
disassembly under /tmp. `audit.json` records evidence. Instruction/stack-site
counts are static context, not cycle attribution. `manifest.json` hashes the
new durable evidence and retained generated artifacts. The source-only Clang
rebuild also validated all 120 frames; GCC recovery is provided but unexecuted.

Production src/simd are unchanged; no commit or push was performed. Phase E
(scheduling/broader workloads) was not part of the authorized 1–4 execution.
