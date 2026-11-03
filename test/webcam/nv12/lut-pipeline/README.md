# Overlap the next AC lookup with current coefficient stores

## Result in the fused NV12 path

Fetching only the next fused entry's bit count early is a small Clang
candidate for accurate-luma mode. With independently trained front-end PGO
and ThinLTO for each source:

| Luma method, reduced fused chroma | Original loop | Minimal lookahead | Change |
|---|---:|---:|---:|
| Accurate | 3.9240 ms | 3.8775 ms | -1.19% |
| Fast | 3.6290 ms | 3.6352 ms | +0.17% |

All three accurate brackets improve (0.61–1.60%); fast directions are mixed.
The current fast winner is unchanged. No production source is modified.

The same fresh-profile comparison against **plain two-hit unrolling** gives
an accurate-mode reduction of 0.95% (3.9011 to 3.8639 ms), with all three
brackets improving 0.74–1.15%. Fast mode changes +0.23% with mixed directions.
Thus early metadata loading adds a small accurate-mode benefit beyond simply
unrolling in this test, but not a demonstrated fast-mode benefit.

These are separate bracket cohorts; compare each candidate against its own
control, not absolute times across the two tables. Both use accurate or fast
native Y IDCT and the previously validated reduced fused chroma kernel.
The entropy changes introduce **no additional output differences**.

## Variants

Each fused table entry can already decode one or two complete AC values.
Two entry hits can therefore produce up to four coefficients.

* **unroll2:** attempt another resident-bit lookup after the first entry's
  stores. This is the ordinary unrolling control.
* **pipeline2:** copy the entire second entry before finishing the first
  entry's coefficient addressing/stores.
* **carry:** retain a prefetched entry across loop iterations, including
  misses. This also starts refill/lookup before current stores.
* **packed:** hold a complete prefetched entry as a 64-bit word, using an
  empty tied-register asm constraint to prevent premature field splitting.
  This is an allocation experiment, not a new CPU instruction.
* **metadata:** fetch only the next table pointer and consumed-bit count
  early, then load the remaining coefficient payload after current stores.
  It uses ordinary C and no asm barrier.

The two-hit variants attempt a second hit only when at least 10 valid bits
are already in the reservoir. They can inspect the next block's resident
prefix, but do not consume bits or write a coefficient across a block boundary.
Misses, EOB, ZRL, long codes, refill and marker rollback retain the existing
paths. The carried variant keeps misses rather than reloading them.

## Initial no-PGO/LTO screening

GCC 13.3 O3 generic and Clang 18.1.3 O3 mtune=znver2; BMI2 on jdhuff.c only.
Positive changes mean slower full JPEG-to-NV12 decode:

| Variant | GCC accurate / fast | Clang accurate / fast |
|---|---:|---:|
| Two hits, ordinary ordering | +2.17% / +2.73% | -2.00% / -1.57% |
| Entire entry fetched early | +7.21% / +7.36% | +0.82% / +0.59% |
| Carried entry | +3.05% / +1.61% | +1.55% / +1.59% |
| Packed early entry | +3.07% / +1.12% | +10.03% / +11.04% |
| Only bit count fetched early | +1.03% / +0.37% | -1.23% / -2.47% |

Packed and metadata rows come from follow-up cohorts with their own controls.
Raw records also retain repeated controls. Whole-entry lookahead lost under
both compilers; minimizing live state was important.

## Assembly evidence and interpretation

`audit.py` recompiles with debug information and checks .text byte-for-byte
against the measured object. Source-annotated assembly confirms that the
early lookups really move before current coefficient stores.

In GCC's entire-entry version, both future coefficient values and its bit
count are loaded and immediately spilled to stack before current stores.
The normal-ordering control loads coefficient payload later. The minimal
version makes just the bit-count byte load early; GCC still spills that byte
in its allocation, while Clang benefits more from the shorter live ranges.
The packed compiler barrier is particularly poor for Clang.

This supports register pressure / extra memory work as a cost of naive
lookahead, but does not attribute exact cycle percentages to individual spills.
Static stack-operand counts are not executed spill counts. CPU out-of-order
execution may already overlap some work across predicted ordinary iterations;
that has not been directly isolated here.

The dependent chain remains `entry → bits consumed → next index → next entry`.
The successful variant hides some next-entry metadata work behind current
stores without keeping all future coefficient fields live at once.

## Profiling and validation

First screen: matched archives change only jdhuff.c.o in libjpeg.a and
libturbojpeg.a; all other members are byte-identical. Three rotated/reversed
rounds, 90 preloaded frames, three passes after full warmup, CPU 0.

Then the promising Clang source was checked in the retained fused pipeline.
Rebuilding jdhuff without PGO slowed that pipeline enough to obscure its small
gain. A matched no-profile control identified this confound. We therefore
trained **original, ordinary-unrolled and minimal-lookahead** sources
independently on the same first 30 frames, through the actual fused path in
both luma modes. The new loops were not fed their old, stale CFG profiles.
The remaining 90 frames are held out for profiling and used for measurement.
They remain one captured scene, not a generalization test across cameras.

Final measurements use three control-candidate-control brackets per mode and
comparison. Loading, allocation and hashing are outside decode timers. CPU
frequency was not fixed. Only JPEG-to-NV12 is benchmarked.

All source variants match native NV12 hashes on all 120 captured frames and
six same-size fixtures: restart every MCU, optimized Huffman tables,
progressive coding, dense AC values, a coefficient at position 63, and all-zero
AC values. Each boundary fixture is decoded twice for sequence-driver reuse.
Both IDCT modes are checked. Freshly profiled original/unrolled/minimal
variants also match on those fixtures through the fused path, and preserve
the prior full-capture fused output/quality metrics exactly.

## Reproduce and artifacts

Requires the retained baseline/profile/fusion builds, common NV12 driver
objects, stock encoder library and local capture from previous experiments.

```sh
python3 test/webcam/nv12/lut-pipeline/build.py
python3 test/webcam/nv12/lut-pipeline/run.py
python3 test/webcam/nv12/lut-pipeline/build.py --only packed
python3 test/webcam/nv12/lut-pipeline/run.py --packed
python3 test/webcam/nv12/lut-pipeline/build.py --only metadata
python3 test/webcam/nv12/lut-pipeline/run.py --metadata
python3 test/webcam/nv12/lut-pipeline/audit.py
python3 test/webcam/nv12/lut-pipeline/fused.py
python3 test/webcam/nv12/lut-pipeline/profile.py
python3 test/webcam/nv12/lut-pipeline/profile.py --unroll-control
```

Candidate directories are not overwritten. Profile preparation resumes
completed builds via profile-build-summary.json. Source-only patches apply to
threshold-pair10, not the unmodified production codec. Compiler pairs have
the same source deltas. JSON summaries/results retain each cohort; assembly,
profiles, generated JPEGs, libraries and executables remain local.
