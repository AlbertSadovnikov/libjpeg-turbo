# Isolated luma IDCT experiment

`luma-idct.cc` extracts quantized Y blocks before timing, then measures only
dequantization, 8x8 inverse DCT, level shift, clipping and pixel stores.
Entropy decoding, chroma, NV12 interleaving and table setup are excluded.
All methods receive the same coefficients and produce contiguous 8x8 blocks.
Stock routines use libjpeg-turbo's runtime SIMD dispatch, not scalar baselines.

The experimental `aan-float4` uses the existing AAN factorization (not a newly
derived transform), floating-point scaled quantization, four independent blocks
in SSE lanes, and final rounding/clipping. Packing coefficients and scattering
pixels are included in its timing. Unlike stock kernels, it has no sparse-block
shortcuts. Its float-to-integer conversion truncates after adding 128.5, then
saturates to bytes. Quantization scaling is prepared outside timing for all
kernels. It requires x86 SSE2, uses no PGO or CPU-specific tuning, and does not
alter production code.

Observed on Ryzen 9 3900X, CPU 0, GCC 13.3 `-O3`, eight camera frames: two
consecutive frames from each of two capture cohorts at VGA and 1080p.
Each reported time is the median of seven trials, at least 200,000 blocks per
trial. Methods run in a fixed order; clocks are uncontrolled. Blocks are
repeated in memory, so these are microbenchmark results, not pipeline predictions.
Output checksums and every sorted trial are saved in `luma-idct-results.jsonl`.

| Kernel | Median ns/block across frames | RMSE vs ISLOW | Maximum absolute error |
|---|---:|---:|---:|
| Stock ISLOW | 27.05–27.30 | 0 | 0 |
| Stock IFAST | 18.53–18.99 | 0.742–1.666 | 4–14 |
| Stock FLOAT | 39.48–43.56 | 0.123–0.132 | 1 |
| Experimental AAN float4 | 39.11–39.57 | 0.122–0.132 | 1 |

Error units are 8-bit luma levels. ISLOW is an accurate integer reference, not
an exact real-valued mathematical oracle. These frames do not establish an
error bound for all legal JPEG blocks. Edge padding pixels are included where
present; selected VGA/1080p luma dimensions are multiples of eight.

The first scalar gather/store revision took approximately 88 ns/block on two
1080p frames. SIMD transposes and saturating packing reduced this to about 39,
but it still loses substantially to IFAST and ISLOW. This candidate is rejected
as a speed improvement. A lower-precision integer SIMD candidate would be a
separate experiment.

Build:

```sh
cmake -S . -B /tmp/luma-idct-build -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_SHARED=OFF -DWITH_TURBOJPEG=OFF -DWITH_TOOLS=OFF -DWITH_TESTS=OFF
cmake --build /tmp/luma-idct-build --target jpeg-static -j 8
g++ -O3 -mavx2 -DNDEBUG -std=c++17 -I/tmp/luma-idct-build -Isrc \
  test/luma-idct.cc /tmp/luma-idct-build/libjpeg.a -o /tmp/luma-idct-bench
taskset -c 0 /tmp/luma-idct-bench path/to/frame.jpg
```

To reproduce the saved cohort, pass the eight `file` paths recorded in the JSONL.

## Derived Q15 integer experiment

`luma-idct-integer.h` retains the real-valued AAN factorization used above,
then derives a different integer approximation. This is not a newly discovered
DCT factorization or a paired implementation of stock IFAST arithmetic.
For each real multiplier c, split c into an integer and a fractional part:

```
m_c(x) = floor(c)*x + floor((round((c-floor(c))*32768)*x + 16384)/32768)
```

The fractional Q15 constants for sqrt(2), 1.847759065, 2.613125930 and
1.082392200 are respectively 13573, 27779, 20091 and 2700. Their integer
parts are 1, 1, 2 and 1. SSSE3 `pmulhrsw` implements the fractional multiply
with rounding, followed by integer additions. Unlike IFAST's multiply scheme,
this requires no two-bit preshift and does not use its 8-bit constants.

Let s[k] = sqrt(2)*cos(k*pi/16) for k>0 and s[0]=1. With B retained
fractional bits, prepare Q'[u,v] = round(Q[u,v]*s[u]*s[v]*2^B).
Dequantization uses a 16-bit multiply; both transform passes retain that
scale. The final pixel is clip((value+2^(B+2)) >> (B+3) + 128), with the
shift performed before adding 128. The initial experiment used B=4; the
current guarded version defaults to B=2. Constants and quantization
are prepared outside timing. AVX2 carries two independent blocks in its
128-bit halves; coefficient assembly, transposes, rounding, clipping and
separate block stores are timed. The single-block version uses SSSE3.
Neither version has sparse-block shortcuts.

On the same eight frames, the final run in
`luma-idct-integer-q4-results.jsonl` measured:

| Kernel | Median ns/block across frames | RMSE vs ISLOW | Maximum absolute error |
|---|---:|---:|---:|
| Stock IFAST | 18.58–18.75 | 0.742–1.666 | 4–14 |
| Derived Q15 single | 19.37–19.59 | 0.221–0.321 | 1–2 |
| Derived Q15 pair | 12.68–12.84 | 0.221–0.321 | 1–2 |

The pair takes 31–32% less time than stock IFAST (1.45–1.47x throughput).
The single-block approximation alone is slightly slower. The speed gain
therefore depends on batching two blocks, not simply changing constants.
These are isolated IDCT measurements, not full JPEG decode measurements.

Earlier precision sweeps are in `luma-idct-integer-results.jsonl` (B=2)
and `luma-idct-integer-q3-results.jsonl` (B=3). Increasing B reduced error
without materially changing the measured cost. Results retain the same
kernel names; use the file names to identify the precision.

SIMD intermediate arithmetic wraps at 16 bits. The benchmark checks every
input block against an independent wide-arithmetic implementation before
timing and exits on output disagreement. All 148,800 cohort blocks matched
the wide output at B=4. Output agreement alone does not prove that individual
intermediates did not wrap.
`luma-idct-integer-check.cc` additionally checks 20,000 deterministic synthetic
blocks, including DC extremes and bounded dense random coefficients, against
the wide oracle and between single/pair implementations. This does not prove
absence of overflow on arbitrary JPEG coefficients or quantization tables;
production integration requires a proven range check or a safe fallback.
No production decoder code is changed.

Build the derived experiment with the library build from above:

```sh
g++ -O3 -mavx2 -DNDEBUG -std=c++17 -I/tmp/luma-idct-build -Isrc \
  test/luma-idct.cc /tmp/luma-idct-build/libjpeg.a -o /tmp/luma-idct-bench
g++ -O3 -mavx2 -std=c++17 -I/tmp/luma-idct-build -Isrc \
  test/luma-idct-integer-check.cc /tmp/luma-idct-build/libjpeg.a \
  -o /tmp/luma-idct-integer-check
/tmp/luma-idct-integer-check
taskset -c 0 /tmp/luma-idct-bench path/to/frame.jpg
```

Use `-DINTEGER_PASS_BITS=2` or `=3` to repeat the precision sweep. The
experiment now requires AVX2, including when running the float comparison.

## Overflow-safe candidate (current default)

The earlier unchecked B=4 kernel fails on coefficients from an actual 8-bit
pixel block. Four white 4x4/black 4x4 quadrants, with matching diagonal
quadrants, encoded by the ISLOW forward DCT with every quantizer equal to 1,
produce a SIMD/wide disagreement on 44 pixels. Stock SSE2 IFAST also fails
on that encoded block. The encoded-pixel regression in
`luma-idct-integer-check.cc` includes this pattern, extrema, cosine sign
patterns, random binary pixels, and random full-range pixels.

The current `aan-q15-safe` uses B=2 and a sufficient admission test for the
16-bit pair kernel. This test accounts for every intermediate, rather than
assuming independently bounded coefficients describe the pixel-derived domain.
Blocks that fail the admission test use the 64-bit scalar implementation;
if one block passes, that block can still use the single-block SIMD kernel.
Thus the guarantee includes every pixel-derived block supported by the
quantizer representation, even when quantization changes coefficient
correlations. It does not require trusting a particular encoder's rounding.

For every intermediate n, propagate an affine expression in the exact scaled
dequantized inputs d[k], plus a bounded rounding error:

```
n = sum(a[n,k]*d[k]) + error[n]
```

A Q15 fractional multiply scales the coefficients and error bound by its
positive fractional constant and adds at most 1/2 to the error bound.
Exact rational propagation through both passes bounds all errors by
3017105/32768 < 93. Set w[k] to ceil(max_n(abs(a[n,k]))), including arithmetic
inside each multiplier and its input. Then the single condition

```
sum(w[k] * abs(coefficient[k]) * scaled_quantizer[k])
    <= 32767 - 93 - final_rounding_bias
```

proves that dequantization, every transform operation, and final rounding fit
in signed 16 bits. The B=2 threshold is 32658. The proof is inductive: admitted
operations implement the wide arithmetic because every earlier operand also
fits. `test/luma-idct-bound.py` derives the weights with exact rational
arithmetic, checks the table compiled into the kernel, and verifies the bounds
for B=2,3,4. It requires only the Python standard library.

The admission test prepares weighted quantizers outside timing. In timed
code it uses absolute coefficients, `pmaddwd`, and saturating partial sums;
the partial-sum clamping cannot turn a failing sum into a passing one. The
-32768 absolute-value special case and weighted quantizers above 32767 force
fallback. Quantizer preparation rejects values that cannot be represented
by the experimental signed-short table. All baseline quantizers 1..255 fit
at B=2,3,4; extended tables are not universally supported by this harness.

The fallback is also bounded: for any signed-short coefficient and table
entry, |d[k]| <= 2^30. The affine coefficient absolute sums are below 130,
so all transform intermediates are below 130*2^30+93 in magnitude. Even
multiplying these values by the largest fractional constant (27779) stays
well within signed 64-bit range. Consequently the guarded kernel has an
arithmetic-range guarantee for every represented input, not just the tested
camera or source-pixel blocks. This guarantees agreement with its defined
integer approximation, not exact reconstruction of the original pixels.

The final B=2 run, including admission and fallback costs, is saved in
`luma-idct-integer-safe-q2-results.jsonl`:

| Kernel | Median ns/block across frames | RMSE vs ISLOW | Maximum absolute error |
|---|---:|---:|---:|
| Stock IFAST | 18.40–18.50 | 0.742–1.666 | 4–14 |
| Guarded Q15 pair, B=2 | 14.69–14.94 | 0.416–1.578 | 3–15 |

This is 19.1–20.6% less time than IFAST. The wide fallback runs on 6 of
148,800 camera blocks. RMSE improves on each frame; maximum absolute error
is not uniformly better. Results are still isolated IDCT measurements,
including contiguous block stores, not full decode throughput.

`luma-idct-integer-safe-q3-results.jsonl` and
`luma-idct-integer-safe-results.jsonl` (B=4) retain the higher-precision guarded
experiments. At B=4 the guard rejects 11–25% of camera blocks, making it
slower than IFAST; B=3 is mixed. B=2 is the current speed candidate.

Validation:

```sh
python3 test/luma-idct-bound.py
# Build and run luma-idct-integer-check using the command above.
```

The check compares 25,760 guarded blocks with the wide oracle, checks the
SIMD admission calculation against a scalar sum, exercises admission
thresholds, and separately compares 20,000 bounded synthetic blocks using
both unguarded SIMD variants. The guarded cases include 2,560 actual JPEG
encodings (each tested in both pair lanes), arbitrary coefficient/table
values, and signed-short extrema. Runs at B=2,3,4 pass. AddressSanitizer and
UndefinedBehaviorSanitizer also pass at B=2 with leak detection disabled
because LeakSanitizer cannot run under this environment's ptrace tracing.

## Odd-part rotation rewrite

`luma-idct-rotation.h` is a separate candidate; the previous kernel remains
available for direct comparison. The original real-valued odd part contains
these terms, with b=x5-x3 and d=x1-x7:

```
z  = 1.847759065*(b+d)
o6 = z-2.613125930*b-o7
o4 = z-1.082392200*d-o5
```

Using 1.847759065=2*cos(pi/8) and
2.613125930-1.847759065=1.847759065-1.082392200=2*sin(pi/8), rewrite as:

```
v  = round_Q15(30274*d) - round_Q15(12540*b)
w  = round_Q15(30274*b) + round_Q15(12540*d)
o6 = (v+v)-o7
o5 = u-o6
o4 = (w+w)-o5
```

Here round_Q15(n) = floor((n+16384)/32768); 30274 and 12540 are
round(32768*cos(pi/8)) and round(32768*sin(pi/8)). There is no shared large
z temporary or multiplier above two. The four fractional multiplies replace
three fractional multiplies and several additions, with a different dependency
structure. The constant quantization and rounding locations change, so this
is a different integer approximation, not a bit-exact algebraic refactoring.

The exact-rational proof script now verifies both candidates. The rotation's
rounding-error bound increases to 1851273/16384 < 113, but several
per-coefficient gains decrease. The guarded B=2 admission threshold is
32638; the same saturation-safe sum calculation and wide fallback strategy
apply. The maximum coefficient absolute sum remains below 130, so the
64-bit fallback range proof also holds. The rewrite does not eliminate the
need for the guard on every possible pixel-derived block.

The final B=2 comparisons in `luma-idct-rotation-q2-results.jsonl` and
`luma-idct-rotation-q2-reverse-results.jsonl` run all eight camera frames in
forward and reversed kernel order. Every method still uses seven trials
and reports its median. Across both orders:

| Kernel, B=2 | Median ns/block across frames/orders | RMSE vs ISLOW |
|---|---:|---:|
| Stock IFAST | 18.43–18.85 | 0.742–1.666 |
| Previous guarded Q15 | 14.74–15.11 | 0.416–1.578 |
| Guarded rotation Q15 | 14.42–14.69 | 0.423–1.580 |

The rewrite takes 1.1–2.8% less time than the previous guarded candidate in
these paired comparisons, and 20.4–22.8% less than IFAST. RMSE is slightly
worse than the previous candidate on every camera frame, but still lower
than IFAST. Maximum error across the cohort remains 15 luma levels.
No camera blocks require fallback, versus six for the previous B=2 kernel.
This is a modest measured improvement, not evidence of a full-decoder gain.

The B=3 forward/reverse files retain the higher-precision comparison:
rotation RMSE is 0.278–0.614 and maximum error is 2–6. It takes
15.42–18.47 ns/block, 4.2–8.9% less time than the previous B=3 candidate.
The hardest VGA cases are close to IFAST's time. The initial B=4 sweep in
`luma-idct-rotation-q4-results.jsonl` remains slower than IFAST because many
blocks need the scalar fallback. B=2 remains the speed candidate.

The regression checker can select either implementation. For rotation:

```sh
python3 test/luma-idct-bound.py
g++ -O3 -mavx2 -DTEST_ROTATION=1 -std=c++17 \
  -I/tmp/luma-idct-build -Isrc test/luma-idct-integer-check.cc \
  /tmp/luma-idct-build/libjpeg.a -o /tmp/luma-idct-rotation-check
/tmp/luma-idct-rotation-check
```

Rotation checks pass at B=2,3,4: 25,760 guarded cases against the wide oracle
and scalar admission calculation, plus 20,000 bounded synthetic comparisons
of both SIMD variants. The encoded quadrant case uses fallback; at B=4 the
unchecked rotation also happens to match its wide output on that particular
case, whereas the earlier unchecked kernel does not. Neither observation
replaces the admission proof. The original B=2 checker still passes.
AddressSanitizer and UndefinedBehaviorSanitizer pass for rotation B=2, with
leak detection disabled for the previously documented ptrace limitation.

The benchmark builds with the existing command and includes both new names:
`rotation-q15-pair` (unchecked) and `rotation-q15-safe` (guarded).
Use `IDCT_REVERSE_ORDER=1 taskset -c 0 /tmp/luma-idct-bench ...` to reverse
the kernel order, and `-DINTEGER_PASS_BITS=3` or `=4` to select precision.
New records include the precision, both fallback counts, and kernel order.

## Three-multiply lifting rotation (rejected for speed)

`luma-idct-lifting.h` implements a separate three-shear approximation to the
same odd-part rotation. With t=tan(pi/16) and s=sin(pi/8), the real-valued
identities are:

```
d1 = d-t*b
w  = b+s*d1
v  = d1-t*w
```

Then v=cos(pi/8)*d-sin(pi/8)*b and
w=sin(pi/8)*d+cos(pi/8)*b. The implementation uses Q15 constants 6518
and 12540, rounding after each shear multiply, then the same doubled odd
terms as the previous rotation. The even part, quantization preparation,
transposes, block layout, clipping and guard structure stay the same.
The timed AVX2 kernel still processes two blocks per call.

The exact-rational proof derives the same integer admission weights as the
previous rotation and a slightly smaller accumulated rounding-error bound:
8114023668395514901059/73786976294838206464 < 110. Thus the B=2 guard
threshold becomes 32641. The per-node coefficient absolute sums remain
below 130, preserving the 64-bit fallback range proof. The previous guard
and proof have not been substituted for this new operation sequence.

The final paired comparisons are saved in
`luma-idct-lifting-q2-results.jsonl` and
`luma-idct-lifting-q2-reverse-results.jsonl`. Both include all eight frames,
seven trials per kernel, and all previous kernels as controls:

| Guarded kernel, B=2 | Median ns/block across frames/orders | RMSE vs ISLOW |
|---|---:|---:|
| Previous rotation | 14.60–15.46 | 0.423–1.580 |
| Lifting rotation | 15.91–16.70 | 0.422–1.579 |

The lifting variant takes 7.6–9.4% more time in the frame-matched comparisons.
Neither B=2 kernel needs fallback on any camera block, so the difference
is not caused by a change in fallback rate. Accuracy changes slightly in
both directions; cohort maximum absolute error remains 15. Later samples
show some clock variation, but the slowdown persists in both kernel orders.
Every kernel's checksums agree between orders.

The likely explanation is the dependent sequence of three multiply-round
operations: removing one multiply from the four-product rotation lengthens
the dependency chain. This is an inference from the algorithm and timings,
not a hardware-counter measurement. Explicit interleaving of two pairs
(four blocks) was not tested and would have additional register-pressure
and layout considerations.

The B=3 forward/reverse result files also retain the higher-precision
comparison. The lifting kernel is 4.8–10.1% slower than the previous rotation
in those frame-matched comparisons. It is not selected as the speed candidate;
the previous guarded rotation remains preferred on this Ryzen 9 3900X.

Validation passes for lifting B=2,3,4: the exact-rational proof, 25,760 guarded
cases against its own wide oracle and scalar admission sum, and 20,000 bounded
synthetic single/pair checks. This includes actual JPEG encodings of source
pixel blocks, the quadrant regression, admission boundaries, and arbitrary
signed-short extrema. AddressSanitizer and UndefinedBehaviorSanitizer pass
for B=2 with the previously documented leak-detection setting. Both existing
B=2 regression variants also pass after adding the new candidate.

```sh
python3 test/luma-idct-bound.py
g++ -O3 -mavx2 -DTEST_LIFTING=1 -std=c++17 \
  -I/tmp/luma-idct-build -Isrc test/luma-idct-integer-check.cc \
  /tmp/luma-idct-build/libjpeg.a -o /tmp/luma-idct-lifting-check
/tmp/luma-idct-lifting-check
```

The benchmark now includes `lifting-q15-pair` (unchecked) and
`lifting-q15-safe` (guarded), plus the lifting fallback count in each record.
The same `IDCT_REVERSE_ORDER` and `INTEGER_PASS_BITS` controls apply.

## DC-only shortcut (rejected for this camera cohort)

`luma-idct-sparse.h` adds `rotation-dc-safe`, a guarded two-block wrapper with
a DC-only shortcut. Classification first checks coefficients 1 and 8, then
ORs all AC coefficients with AVX2 if those two are zero. Coefficient 0 is
masked out; coefficient 8 and every other AC position remain part of the
full check. Both scans and branches are inside timing, with no precomputed
block flags.

A DC-only block reduces exactly to:

```
pixel = clip(((coefficient[0]*scaled_quantizer[0] + bias) >> shift) + 128)
```

The shortcut broadcasts that byte to two 32-byte stores. It needs no
admission test: the product of any two signed-short inputs has magnitude
at most 2^30, and the rounding bias, shift and level shift fit in signed
32 bits. All fractional multiplies elsewhere would receive zero, so this
is bit-exact with the wide rotation kernel. The general transform's existing
proof and guard are unchanged. For a mixed pair, only the DC block uses the
fill; the other uses the single-block SIMD kernel or its wide fallback.
If neither is DC-only, the wrapper calls the existing guarded pair kernel.

The saved files `luma-idct-sparse-q2-results.jsonl` and
`luma-idct-sparse-q2-reverse-results.jsonl` include sparsity statistics and
timed comparisons in both kernel orders. Across the eight camera frames:

- DC-only: 960 of 148,800 blocks (0.645% overall; 0.063–1.139% per frame).
- Both blocks DC-only: 229 pairs; exactly one DC-only: 502 pairs.
- Coefficients confined to the top-left 2x2 and 4x4, zero vertical-AC
  columns, and first-row-only counts are also recorded, outside timing.
- The top-left 4x4 category contains 2.94–25.87% of blocks per frame,
  offering more potential than DC-only classification for a later experiment.

| Kernel, B=2 | Median ns/block across frames/orders |
|---|---:|
| Guarded rotation | 14.48–14.84 |
| Guarded rotation with DC shortcut | 14.63–15.33 |

The shortcut adds a median 2.8% to the frame-matched times; the range is
approximately unchanged to 4.8% slower (one comparison differs by -0.02%,
within normal timing variation). The frequency is too low to offset checking
and dispatch overhead on this footage. The existing guarded rotation remains
preferred. Output checksums and all recorded error metrics are identical
between the two variants on every frame, and all kernel checksums agree
between forward and reversed benchmark order. This rejects the DC-only
wrapper for this cohort, not sparsity shortcuts for all JPEG workloads.

The regression checker now also compares the DC wrapper and classifier
against the wide rotation oracle and a scalar all-AC-zero check. It adds
54,540 cases covering both pair lanes, both-DC and mixed pairs, every AC
coefficient position, signed-short DC/quantizer extremes, clipping and zeros.
In total it checks 80,300 guarded block cases, plus the existing 20,000
bounded synthetic single/pair cases. Runs at B=2,3,4 pass; B=2 also passes
AddressSanitizer and UndefinedBehaviorSanitizer with the previously documented
leak-detection setting.

The existing checker command with `-DTEST_ROTATION=1` exercises this path.
The benchmark includes `rotation-dc-safe`; its JSON records add `dc_blocks`,
`dc_pairs`, `dc_mixed_pairs`, `low2_blocks`, `low4_blocks`, `zero_ac_columns`,
and `first_row_only_blocks`.

## Top-left 4x4 support shortcut (rejected for this camera cohort)

`luma-idct-low4.h` specializes the rotation for blocks with zero coefficients
outside the top-left 4x4 region. This still reconstructs all 64 pixels of an
8x8 block; it is not the scaled-down 4x4-output JPEG IDCT.

Each 1D transform has x4=x5=x6=x7=0. Its even part simplifies to:

```
t  = round_Q15(13573*x2)
e0 = x0+x2; e3 = x0-x2
e1 = x0+t;  e2 = x0-t
```

The odd part retains the previous rotation's rounding operations with
b=-x3 and d=x1. In particular, rounding a negative product stays in its
original location; moving the minus sign outside rounding would change
halfway cases. The first pass loads/dequantizes only four coefficients from
each of the first four rows. A dedicated 8x4 transpose supplies the four
nonzero inputs of the second pass, followed by a full output transpose and
stores. Both single-block SSE and paired AVX2 implementations are included.

The proof script now also performs a symbolic identity check with rounding
represented as opaque expressions. It verifies that all eight reduced
outputs equal the full rotation outputs exactly and that every reduced
arithmetic intermediate also occurs in the full rotation. Thus the existing
admission bound suffices: specialization removes operations without creating
new intermediate values. Transpose placement and lane handling are checked
against the wide oracle in the regression suite.

Two timed dispatch policies were tested:

- `rotation-low4-pairs-safe` specializes only when both blocks qualify;
  mixed-support pairs retain the dense guarded pair kernel.
- `rotation-low4-mixed-safe` also specializes a single qualifying block,
  processing its partner individually with the dense SIMD or wide kernel.

Both retain the range guard and wide fallback. Scans, guard checks, branches,
coefficient packing, transposes and stores are inside timing. No support flags
are prepared outside timing. The first classifier used scalar early exits;
the final classifier uses only SIMD masking/OR and a zero test. Initial
results are retained in the `luma-idct-low4-q2*-early-results.jsonl` files;
removing the early branches substantially reduced its observed overhead.

The final files are `luma-idct-low4-q2-results.jsonl` and
`luma-idct-low4-q2-reverse-results.jsonl`. Of 148,800 camera blocks, 28,474
(19.14%) qualify. There are 7,760 pairs where both qualify and 12,954 pairs
where exactly one qualifies. The per-frame qualifying fraction remains
2.94–25.87%.

| Kernel, B=2 | Median ns/block across frames/orders | Extra time vs dense rotation, matched frames |
|---|---:|---:|
| Dense guarded rotation | 14.45–14.69 | — |
| Specialize qualifying pairs only | 15.30–16.07 | 5.5–10.5% (median 7.6%) |
| Specialize mixed pairs as well | 15.41–18.30 | 6.4–26.5% (median 14.3%) |

Both policies lose on every frame in both kernel orders. Classification and
dispatch costs outweigh the savings at these frequencies; processing mixed
pairs individually further loses the batching benefit. These timings compare
complete dispatch paths, not standalone reduced kernels, and do not separate
branch misses from other costs. The previous dense guarded rotation remains
the preferred candidate. Both new methods have exactly the same output
checksums and recorded error metrics as the dense rotation on every frame;
all benchmark kernel checksums agree between forward and reversed order.

The regression checker adds 200,000 low4-specific block cases: independent
pair lanes, dense values within the permitted support, and every excluded
coefficient position set to either 1 or -32768. It checks both policies and
the classifier against the wide oracle and a scalar support scan, alongside
the existing encoded-pixel, DC, boundary and arbitrary-coefficient cases.
All 280,300 guarded block cases pass at B=2,3,4, plus the existing 20,000
bounded synthetic single/pair comparisons. B=2 passes AddressSanitizer and
UndefinedBehaviorSanitizer with the previously documented leak-detection
setting. The extended exact-rational/symbolic proof script also passes.

Use the existing checker command with `-DTEST_ROTATION=1`; the benchmark
includes both new kernel names and records `low4_pairs` and
`low4_mixed_pairs` in addition to the earlier support counts.

## Compensated arithmetic and deliberate modular cancellation

Eight further arithmetic experiments, their derived tables and range proofs,
are documented in [luma-idct-arithmetic.md](luma-idct-arithmetic.md).
The useful results are a modest B=2 speed gain using a compensated 45/32
sqrt(2) approximation, and a stronger B=3 quality/speed option that permits
intermediate addition/subtraction wrap only between proved-safe nonlinear
checkpoints. The latter preserves rotation output exactly while reducing
camera fallback from 1,683 blocks to 51.
