# Manual BMI intrinsics versus compiler-selected BMI2

2026-10-31, Ryzen 9 3900X, GCC 13.3. Control is the current winning decoder:
scalar refill + two-symbol AC LUT + pre-shifted thresholds, with `-mbmi2` only
for `jdhuff.c`. Production codec sources are unchanged.

**Recommendation: keep compiler-selected BMI2; do not broadly replace it with
manual intrinsics.** Forced BZHI is a small, workload-dependent candidate, not
a confirmed general improvement. BEXTR loses. A simpler C sign-extension
formula lowers instruction count but regresses in the sequence fast-IDCT case.

## Source audit and candidate choice

The [instruction audit](../bmi-current/instruction-audit/README.md) maps exact
measured code to source with byte-identical debug `.text`. The fast MCU loop
already has 13 SHRX and six SHLX sites. Of 53 BMI2 sites in the whole object,
19 are fast-path sites; 19 are setup; the remainder are slow paths/helpers.
The only compiler-selected BZHI is in the out-of-line slow Huffman helper.

Candidates:

- **bzhi-mask:** replace `GET_BITS`'s dynamic low-bit mask with `_bzhi_u32`.
  Keep ordinary C right shifts so GCC still selects SHRX. Same `-mbmi2` flags
  as the control; applies to fast and slow receive operations in jdhuff.c.
- **extend-c:** no explicit intrinsic. Rewrite JPEG sign extension from its
  shifted-threshold formula to `x - (((x >> (s-1)) - 1) & ((1 << s) - 1))`.
  Valid inputs have `s > 0` and x already masked to s bits. This exposes reuse
  of the receive mask, but also changes the data-dependency graph.
- **bextr-peek:** use GCC's packed-control `__bextr_u64` for fast-path PEEK.
  The reader guarantees enough bits. Control is `start + (length << 8)` =
  `bits_left + 255*length`. This avoids unnecessary start/length masking and
  uses one BEXTR for contiguous extraction. Requires BMI1, so compile under
  the combined BMI1/LZCNT/BMI2 tier and measure an unchanged same-tier control.

Fast MCU static instruction sites, source-mapped independently for each binary:

| Variant | SHRX | SHLX | BZHI | SARX | BEXTR |
|---|---:|---:|---:|---:|---:|
| Compiler BMI2 | 13 | 6 | 0 | 0 | 0 |
| Forced BZHI | 13 | 4 | 2 | 0 | 0 |
| C sign-extension rewrite | 13 | 2 | 0 | 2 | 0 |
| BEXTR peek | 5 | 6 | 0 | 0 | 7 |

Thus a source-level intrinsic does change some emitted instructions, but GCC
already handles the dominant variable shifts. It also selects SARX from the
plain C rewrite without an explicit intrinsic. Counts alone do not establish
lower latency/uop cost or a better critical path.

## Matched-archive correctness and measurement

Copy control codec archives and replace only `jdhuff.c.o`, for both libjpeg and
TurboJPEG. Check every other member byte-for-byte. Same generated headers and
per-library flags; source deltas are reviewed in the retained patches. The
unchanged combined-feature build provides a same-ISA control for BEXTR.

Each of the three candidates passed 332 CTest tests, exact decoded pixels for
all 120 captured frames, persistent decoder reuse in five modes with mixed
baseline/progressive inputs, and protected source boundaries (five images, ten
chunk sizes). NV12 hashes agree for each reconstruction method. The combined
control was also checked by the shared runner. Source-mapped debug builds have
identical machine-code text to their respective measured release objects.

Five rotated/reversed 100-frame rounds after five warmups, native first, then
hardware. CPU 0. Gated user cycles/instructions/branches/branch-misses run at
100% with no multiplexing. Warmup/setup excluded from entropy aggregation;
NV12 includes complete decode. Frequency was not fixed. Hardware wall time
includes control waits and is not used as latency.

| Variant | Accurate NV12 ms | Fast NV12 ms | Accurate cycle change | Fast cycle change |
|---|---:|---:|---:|---:|
| Compiler BMI2 control | 4.3895 | 4.0307 | baseline | baseline |
| Unchanged combined-feature control | 4.3654 | 3.9892 | -0.72% | -1.09% |
| Forced BZHI | 4.3986 | 4.0144 | -0.28% | -0.44% |
| C sign-extension rewrite | 4.3749 | 4.0045 | -0.75% | -1.42% |
| BEXTR peek | 4.4202 | 4.0914 | +0.35% | +2.43% |

Negative cycle change means fewer cycles. The unchanged combined-tier control
varies from its earlier cohort; tiny differences should not be promoted solely
from one set of medians. Against that same-ISA control, BEXTR costs **1.08% more
accurate cycles, 3.56% more fast cycles**. It also adds about 342,661 retired
branches/frame despite slightly fewer instructions. All five BEXTR hardware
pairs regress versus the BMI2 control in both NV12 modes.

| Entropy-only measurement | Compiler BMI2 | Forced BZHI | C rewrite | BEXTR |
|---|---:|---:|---:|---:|
| Instructions/frame | 19.443M | 19.275M | 19.135M | 19.213M |
| Cycle change | baseline | -0.52% | +0.65% | +1.51% |

BZHI saves about 167k retired instructions/frame and lowers isolated entropy
cycles in all five pairs. This is modest; accurate NV12 pairs vary in direction.
The C rewrite removes more instructions but isolated entropy gets slower.
Its sign decision depends on the extracted value's variable shift rather than
an independently computable size threshold, a changed dependency worth noting;
these counters do not isolate that effect from code layout/register allocation.

## Full sequence confirmation

For BZHI and the C rewrite, replay 120 preloaded frames, three measured passes
after one full warmup pass, three control-candidate-control brackets per IDCT
method. Rotate candidate order. Controls are averaged at each bracket's ends.
No disk I/O, allocation or hashing inside decode timers. Entire-sequence NV12
hashes agree. The sequence executable has a different link layout and input
working set from the single-frame driver; it is an important robustness check.

| Mode/candidate | Bracketed control ms | Candidate ms | Time change |
|---|---:|---:|---:|
| Accurate, BZHI | 4.3182 | 4.3606 | +0.98% |
| Accurate, C rewrite | 4.2908 | 4.2692 | -0.50% |
| Fast, BZHI | 3.9851 | 3.9415 | -1.09% |
| Fast, C rewrite | 3.9262 | 4.3426 | +10.61% |

Positive time change means slower. BZHI accurate brackets are -4.39%, +0.49%,
+0.96% time reductions: the first is a regression/outlier, the other two improve.
Fast BZHI reductions are -0.24%, +1.67%, +1.80%. This is a hint of a small fast-
IDCT-specific gain, not a reliable across-method improvement.

The C rewrite accurate brackets improve 0.69%, 0.74%, 0.08%, but fast mode
regresses in **all three** by 11.12%, 9.17%, 11.53%. Output matches. The cause
has not been isolated: differing code layout/dataflow and the larger working
set can change interactions with IDCT. Do not attribute 10.6% solely to one
instruction or algebraic identity. This implementation is not promoted.

## Reproduction and artifacts

```sh
python3 test/webcam/bmi-intrinsics/build.py
python3 test/webcam/bmi-current/audit.py --manual
python3 test/webcam/zenjpeg-ideas/run.py --config test/webcam/bmi-intrinsics/experiment.json
python3 test/webcam/bmi-intrinsics/sequence.py
```

Audit `--manual` requires the candidate builds. Scripts rely on the previously documented `/tmp` control builds,
embedded object and Google Benchmark artifacts. Build preparation refuses
existing source directories. `*.patch` files are deltas against threshold-pair10;
`*-complete.patch` files reconstruct the complete decoder source from the
untouched checkout, but the CPU flags listed in `experiment.json`/build.py are
still required. Do not apply both kinds of patch or mix alternatives.

`summary.json`, `results.json`, `validation.json`, `isolation.json` and
`sequence/summary.json` preserve the exact records. Detailed assembly, samples,
logs and perf data remain local. No production intrinsic or runtime dispatch
was introduced. These are measured C/GCC/Zen-2 candidates, not a claim that
intrinsics never help another algorithm, compiler or CPU.
