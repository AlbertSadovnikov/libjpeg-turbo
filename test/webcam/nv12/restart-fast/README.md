# Restart-aware fast entropy prototype

Retain a **separate candidate for restart-enabled camera workloads**, with
25.86% less LifeCam 1080p decode time under Clang and 26.05% under GCC versus
the previous optimized exact path. Whole NV12 and every tested coefficient
remain unchanged. Existing defaults are preserved: the candidate still has
a small measured non-restart cost, and short sparse restart intervals regress.
No production src/simd edit, commit or push was made.

## Separate confirmation

Negative means less time:

| Input, 1080p | Compiler | Previous exact path | Restart-aware | Time change |
|---|---|---:|---:|---:|
| Logitech C930e | clang | 3.5400 ms | 3.5874 ms | +1.34% |
| Logitech C930e | gcc | 3.5510 ms | 3.5751 ms | +0.68% |
| LifeCam Studio | clang | 5.3823 ms | 3.9904 ms | -25.86% |
| LifeCam Studio | gcc | 5.4809 ms | 4.0532 ms | -26.05% |

Three independent control/candidate/control brackets, 60 passes over each
camera's twelve 1080p high-requested-rate frames, pinned CPU 0 on Ryzen 9
3900X. Every LifeCam confirmation bracket improves. Both compiler means on
Logitech increase, with mixed magnitude, so do not claim unchanged non-restart
performance merely because its original C routine is retained.

Primary revised cohort: three brackets, 20 passes, VGA/720p/1080p LifeCam and
VGA/1080p Logitech. LifeCam improves approximately 23–27% versus the previous
optimized path. Original-versus-identical-original 1080p noise means are
+0.27% Clang and -0.28% GCC; individual brackets remain saved. Confirmation
uses longer repetitions and is a separate cohort, not pooled with primary.
The remaining Logitech means are +1.34% Clang / +0.68% GCC; this is much
smaller than the first implementation's regression, but not a zero-cost proof.

O3, matched LTO (Clang ThinLTO/GCC LTO), no PGO, no explicit CPU tuning,
unchanged BMI2 entropy and shared native AVX2 Y/UV/packing support. GCC retains
its deferred-field source expression and default protection settings. Loading,
allocation, output hashing and diagnostics are outside timed decode regions.
Compilation, validation, diagnostics and timing run sequentially without other
agent CPU workloads. Capture rate is not decode throughput or encoder speed.

## Against public stock-fast decoding, fresh primary cohort

| LifeCam size | Compiler | Stock fast | Restart-aware exact | Less time |
|---|---|---:|---:|---:|
| 640x480 | clang | 1.2330 ms | 0.8655 ms | 29.81% |
| 640x480 | gcc | 1.2878 ms | 0.8631 ms | 32.98% |
| 1280x720 | clang | 3.7361 ms | 2.5853 ms | 30.80% |
| 1280x720 | gcc | 3.8876 ms | 2.5811 ms | 33.61% |
| 1920x1080 | clang | 6.0909 ms | 3.9944 ms | 34.42% |
| 1920x1080 | gcc | 6.3345 ms | 4.0316 ms | 36.35% |

These compare complete exact NV12 with matched stock/compiler settings and
identical inputs. Every stock comparison bracket improves. The 1080p stock
reductions are 34.42% Clang and 36.35% GCC. These are new LifeCam measurements,
not percentages added to the earlier Logitech headline or a universal feed
speedup. Same one CPU; short temporal capture sets and workload coverage remain
limits. Accurate-IDCT equivalence is not implied by stock-fast equality.

## Algorithm and state safety

The old dispatcher forced every restart-bearing scan through its slow entropy
routine. The new routine allows fast attempts before the interval's final MCU,
while retaining the conservative per-MCU source-byte budget plus eight-byte
lookahead allowance. It preserves ordinary process_restart behavior and DC
predictor resets, then keeps the final MCU on the marker-aware slow decoder.
Intervals of one MCU naturally use the slow path throughout.

Fast GET_BYTE stops immediately when it encounters a marker, including legal
FF fill runs. It does not fabricate zero coefficient bits, consume the marker
or commit local source/bit/DC state. Before retry, clear every attempted output
block individually and call the original slow decoder. Individual block
clearing is essential because full-image coefficient arrays are not one
contiguous MCU allocation. The null-output case skips clearing. Constant
128-byte clears compile inline; ordinary controller AVX2 clearing is unchanged.
`audit.json` and `separate-audit.json` check for no out-of-line memset/jzero
calls in the relevant routines, and absence of PGO metadata/options.

No restart count is decremented on suspension; the existing successful-MCU
accounting and marker handling remain. JPEG tables, dimensions, sample values
and marker positions are runtime inputs. There is no camera-ID check,
Huffman-table specialization, re-encoding, extra quality loss or parallel
execution in this experiment.

## Two implementations, one evidence-driven revision

`clang-restart.patch` / `gcc-restart.patch` are the first version. They modify
the shared fast reader and dispatcher. All correctness gates pass and LifeCam
improves roughly 22–26%, but the non-restart Logitech code slows (about 3–4%
with Clang at 1080p). Those raw results remain in unprefixed JSON. Do not stack
or select that implementation.

`clang-separate-restart.patch` / `gcc-separate-restart.patch` are the retained
revision. Preserve the original private fast routine and dispatcher source,
and select a separate restart-aware dispatcher once per sequential scan in
start_pass_huff_decoder. Decoder reuse therefore reselects after DRI changes;
progressive entropy retains its existing module. A second private fast routine
uses the marker-aborting macro expansion. This duplicates some code in the
prototype to avoid coupling the two source paths; it is a maintainability
tradeoff for review, not a production-ready refactor.

The original C routine remains, but its generated code is not byte-identical:
the compiler changes inlining/outlining with the new call graph. The remaining
Logitech penalty is measured above. Assembly identification follows both the
jinit default and the actual per-scan assignment; looking only at jinit would
misidentify the active restart routine. Full disassembly stays under /tmp.

The Clang patch applies to the current source recovered by lto-only/codec.patch;
the GCC patch applies after gcc-deferred-loads/deferred.patch. Build scripts
verify only jdhuff.c.o changes in either codec archive. No retained PGO archive
or trained profile is linked. Diagnostic counter objects are never timed.

## Validation

Both implementations pass, under both compilers:

- All 2,148 new camera frames over 179 modes / 29 camera-resolution groups,
  against saved stock-fast-exact NV12 reports; accurate/fast methods, modes
  1/2/3, generic edge fallbacks and padded destinations retain output/padding.
- 51 coefficient-preserving synthetic JPEGs: ordinary, dense, zero-AC and
  coefficient-63-tail images; DRI 1, 2, 3, 7, 31, 119, 120, 121, 241 and 65535;
  optimized Huffman tables at DRI 3/120; and legal marker fill bytes.
- Alternating cameras at matched VGA/720p/1080p dimensions and mixed restart,
  non-restart and progressive frames to exercise table/callback refresh.
- **2,325 literal coefficient/table streams** match the reference: all new
  captures, 120 original captures, 51 new fixtures and six original fixtures.
  This exercises noncontiguous virtual coefficient arrays as well as raw
  reconstruction buffers; it is not just a last-MCU or final-image hash.
- Full versus suspended arrays match literally on 23 selected inputs with
  97/4093-byte exposure increments. Both compiler candidates encounter
  **127,934 forced suspensions** per harness run; control/candidate full output
  hashes agree. Odd-column resume counts can differ and are not a correctness
  criterion. Headers/startup are fed before restricting input, so suspended
  progressive startup is outside this claim.

No warning/error differences appeared on the valid tested inputs. This does
not claim exhaustive malformed JPEG, other precision or other sampling tests.

## Untimed path counts and retry coverage

On the twelve LifeCam 1080p high-requested-rate frames, 192,016 of 194,400 MCUs
commit via the fast path (**98.77%**), with seven speculative marker retries
and 2,384 slow calls. The previous build used zero fast calls. Logitech path
counts are unchanged. The zero-AC/DRI-3 fixture forces 2,171 retries and the
marker-fill fixture 60, so cleanup/rollback is actively exercised, not merely
a dormant branch. Counts agree between both implementations.

These are separate untimed diagnostic builds that skip reconstruction, not
valid NV12 timings or PGO/training profiles. See diagnostics JSON and patch.

## Short-interval and sparse-scene limits

Three brackets each, fifty passes per invocation; positive means slower:

| Scene | Clang time change range | GCC time change range |
|---|---:|---:|
| ordinary-rst1.jpg | +2.58% to +2.82% | +0.66% to +1.20% |
| ordinary-rst2.jpg | -10.27% to -9.63% | -10.54% to -9.38% |
| zeroac-rst3.jpg | +7.30% to +7.78% | +6.41% to +8.17% |
| dense-rst2.jpg | -30.45% to -30.21% | -30.52% to -30.28% |
| ordinary-fill-rst3.jpg | -15.63% to -13.09% | -15.92% to -13.44% |

The sparse DRI-3 case regresses about 7–8%; short intervals can cause enough
speculative retries and replay to erase the fast-path gain. DRI-1 remains
fully slow and shows a small overhead. Conversely dense DRI-2 improves about
30%. Do not advertise universally improved restart handling. Both actual
cameras remain byte-exact, but keeping this as a separate restart-workload
candidate is deliberate. One source implementation and one revision were
tried; no third tuning variant was added or losing changes silently stacked.

## Artifacts and reproduction

`candidates.json` records separate `/tmp/mjpeg-restart-fast/clang-nv12` and
`gcc-nv12` aliases, explicit mode **3**, and hashes. The established exact-fast,
reduced-UV and GCC-deferred aliases are untouched. For example:

```
taskset -c 0 /tmp/mjpeg-restart-fast/clang-nv12 fast 3 20 JPEG...
```

Build/test scripts require the saved next-round baseline support, both camera
capture batches, geometry-aware drivers from multi-camera, and GCC deferred
candidate. Large generated files and binaries remain under /tmp. Full pipeline:

```
python3 test/webcam/nv12/restart-fast/build.py
python3 test/webcam/nv12/restart-fast/prepare-tests.py
python3 test/webcam/nv12/restart-fast/audit.py
python3 test/webcam/nv12/restart-fast/check.py
python3 test/webcam/nv12/restart-fast/diagnostics.py build
python3 test/webcam/nv12/restart-fast/diagnostics.py run
python3 test/webcam/nv12/restart-fast/run.py
# Retained separate-dispatch revision, with fresh validation and cohorts:
python3 test/webcam/nv12/restart-fast/build.py --separate
python3 test/webcam/nv12/restart-fast/audit.py --separate
python3 test/webcam/nv12/restart-fast/check.py --separate
python3 test/webcam/nv12/restart-fast/diagnostics.py build --separate
python3 test/webcam/nv12/restart-fast/diagnostics.py run --separate
python3 test/webcam/nv12/restart-fast/run.py --separate
python3 test/webcam/nv12/restart-fast/run.py --separate --confirm
python3 test/webcam/nv12/restart-fast/scene-run.py --separate
python3 test/webcam/nv12/restart-fast/choose-candidates.py
python3 test/webcam/nv12/restart-fast/report.py
```

Raw per-round JSON, source patches, fixture/input hashes, audits and compiler
flags are kept here; manifest.json hashes durable evidence and generated
artifacts. No build, profiler or validation runs concurrently with timing.
Further work before a general default would need to address the non-restart
code-generation cost and sparse short-interval regressions, plus broader scene
and CPU coverage. Parallel restart-row decoding was not attempted.
