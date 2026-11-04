# Arithmetic approximation experiments

These experiments extend the isolated IDCT work in `luma-idct.md`. All methods
produce full 8x8 luma output. The timed SIMD path processes two blocks per AVX2
call and includes dequantization, packing, transposes, stores, guard checks and
any scalar fallback. Production decoding code is unchanged.

Eight variants are implemented in `luma-idct-arithmetic.h`. They share one
transform definition instantiated for SSE, AVX2 and independent-width scalar
arithmetic; quantization preparation and range tables are specific to each
variant. The current cosine/sine rotation is the baseline.

## Attempts and measurements

Seven-trial median measurements on the same eight camera frames, Ryzen 9
3900X, CPU 0, GCC 13.3, -O3 -mavx2. Both forward and reversed kernel orders
are saved. Clocks remain uncontrolled. Every kernel checksum agrees between
orders. Error units are 8-bit luma levels; ISLOW is the reference.

B=2 means two retained fractional bits. Across frames and both orders:

| Variant | Arithmetic change | ns/block | RMSE vs ISLOW | Cohort max error |
|---|---|---:|---:|---:|
| Existing rotation | Baseline | 14.36–14.58 | 0.423–1.580 | 15 |
| comp-control | Same arithmetic, analytical gain fit | 14.52–14.76 | 0.423–1.580 | 15 |
| root-3over2 | sqrt(2)*x -> x+(x>>1) | 13.96–14.23 | 1.382–2.436 | 26 |
| root-45over32 | x+(x>>1)-(x>>4)-(x>>5) | 14.05–14.36 | 0.437–1.576 | 15 |
| rotation-1-3over8 | cos(pi/8) -> 1; sin(pi/8) -> 3/8 | 13.29–13.63 | 2.413–3.538 | 51 |
| root-and-rotation | root-3over2 plus rotation-1-3over8 | 13.06–13.32 | 1.625–2.475 | 31 |
| modular | Same arithmetic/output, checkpoint-only guard | 14.43–14.75 | 0.423–1.580 | 15 |
| root-91over64 | x+(x>>1)-(x>>4)-(x>>6) | 14.08–14.32 | 0.443–1.609 | 14 |
| root-181over128 | x+(x>>1)-(x>>4)-(x>>6)-(x>>7) | 14.40–14.68 | 0.446–1.585 | 15 |

All shifts above are arithmetic floor shifts on signed inputs, applied
separately. They are not equivalent to one correctly rounded multiply by
the combined rational constant. The cheap rotation's 3/8 multiply is
(x>>1)-(x>>3). Whole parts and subtractions are kept in the documented order.
The closer 181/128 real constant does not give the lowest measured error,
because separate shifts also change integer rounding bias.

The 45/32 variant takes 0.75–3.28% less time than the existing rotation in
each frame/order comparison. It is a modest speed/accuracy tradeoff, not a
uniform quality improvement. 91/64 has similar speed but generally higher
RMSE. 181/128 offers no consistent speed gain. The two aggressive rotation
variants save more time but introduce substantially larger errors than IFAST
on most camera frames; they are not preferred.

The generic comp-control has identical camera outputs to the existing
rotation but slightly different measured timing, despite the same arithmetic.
Code generation/layout and uncontrolled clocks limit claims about differences
this small. Frame-matched comparisons and reversed order reduce, but do not
eliminate, those limitations.

## Analytical quantization compensation

`luma-idct-arithmetic.py` derives all tables without reading any camera data.
Let M[:,k] be the real-valued transform's output for unit frequency k, with
its actual dyadic/Q15 constants but rounding disabled. The desired scaled
cosine column is N[r,0]=1 and N[r,k]=sqrt(2)*cos((2r+1)*k*pi/16) for k>0.
Choose the least-squares frequency scale

```
a[k] = dot(M[:,k], N[:,k]) / dot(M[:,k], M[:,k])
scaled_quantizer[u,v] = round(Q[u,v] * a[u] * a[v] * 2^B)
```

This fits the gain of each basis column, then folds the factors into table
setup outside timing. It cannot correct a wrong basis direction or all
input-dependent rounding error. The modular variant retains the original
quantizer table exactly, so its output comparison is bit-exact.

A separate B=2 run with `IDCT_UNCOMPENSATED=1` tests the same arithmetic with
the original AAN scales. Compensation reduces RMSE by 3.3–11.1% for root-3over2,
2.4–19.1% for rotation-1-3over8, and 6.6–30.8% for root-and-rotation across
frames. These remain poor enough to reject as quality-preserving speed gains.
For 45/32 the improvement is only 0–0.6%, and for the near-exact/control
variants it is negligible or mixed after table rounding. Compensation helps
but does not turn an arbitrary cheap transform into an accurate DCT.

## Useful modular-overflow result

The original guard demands that every intermediate fits signed 16 bits.
That is stronger than necessary for a graph of wrapping additions and
subtractions. Such operations compute the wide result modulo 65536; overflow
can cancel before the next operation that needs the signed interpretation.

The modular certificate therefore bounds only:

1. Inputs to fractional multiplies (and arithmetic shifts, where present).
2. Final transform values including the final rounding bias.

All intervening additions/subtractions may wrap. If a checkpoint's wide
value fits signed 16 bits, the stored residue has exactly the correct signed
interpretation there. This gives an induction over the nonlinear checkpoints:
each rounded multiply is correct, and linear stretches remain congruent until
the next checkpoint. Final clipping receives a correct signed value.
This is deliberate use of defined SIMD wrapping, not undefined scalar overflow.

The certificate uses the same exact affine/rational propagation as before,
but computes per-frequency gain weights over the required checkpoints rather
than all nodes. The rounding-error budget remains 113 for this variant.
Saturating partial sums in the admission implementation prevent the guard
calculation itself from wrapping into a false acceptance. Unsupported ranges
still use 64-bit arithmetic. Table values and coefficients remain signed short.

The best quality/speed balance in this batch is B=3 with the modular guard:

| Guarded B=3 kernel | ns/block across frames/orders | RMSE vs ISLOW | Cohort max error | Fallback blocks |
|---|---:|---:|---:|---:|
| Original rotation guard | 15.32–18.52 | 0.278–0.614 | 6 | 1,683 / 148,800 |
| Modular guard | 14.52–15.09 | 0.278–0.614 | 6 | 51 / 148,800 |

This is 5.1–19.1% less time than the original guard at the same precision,
with identical output checksums and all error metrics on every frame.
It runs near the old B=2 timing while materially improving reconstruction
accuracy. This is the preferred new quality/speed option; 45/32 at B=2 is
an alternative when the last few percent of time matter more than the modest
error increase. These options have not been combined in this experiment.

At B=2 the original rotation has no camera fallbacks, so the modular guard
gives no useful speed benefit. At B=4 it cuts fallback from 16,763 to 5,977
blocks and takes 17.96–25.85 ns/block versus 24.86–37.42; this remains too
slow on some frames to replace B=3 as the balanced choice.

## Verification and reproduction

`luma-idct-arithmetic.py` verifies the generated tables using exact rational
arithmetic for range bounds, and floating-point analytical basis columns for
compensation. Every variant has a maximum intermediate coefficient absolute
sum below 256 and an error bound below 256. With |dequantized input| <= 2^30
for signed-short inputs, even the 64-bit fallback's fractional products stay
well within its range. The range proof guarantees agreement with each defined
integer approximation; it is not a global bound on error relative to ISLOW.

All eight variants pass 280,300 guarded block cases and 20,000 bounded
synthetic single/pair comparisons at B=2. Cases include actual JPEG encodings,
source-pixel extrema, DC/mixed pairs, low4 support boundaries, every AC
position, scalar-vs-SIMD admission sums and arbitrary signed-short extrema.
Selected higher-precision checks also pass: 45/32 at B=3 and modular at B=3,4.
The modular tests separately require bit-exact agreement with the original
wide rotation. An audited wide trace on admitted blocks counts 852 out-of-range
intermediate additions/subtractions at B=3 and 908 at B=4, while checking every
fractional-multiply input and final rounding input fits. SIMD still agrees
with the wide output in those cases. AddressSanitizer and UndefinedBehaviorSanitizer
pass for 45/32 B=2 and modular B=3 (leak detection disabled for the existing
ptrace limitation).

```sh
python3 test/luma-idct-bound.py
python3 test/luma-idct-arithmetic.py
# Only when intentionally changing analytical constants/table generation:
# python3 test/luma-idct-arithmetic.py --generate

g++ -O3 -mavx2 -DTEST_ARITHMETIC=5 -DINTEGER_PASS_BITS=3 -std=c++17 \
  -I/tmp/luma-idct-build -Isrc test/luma-idct-integer-check.cc \
  /tmp/luma-idct-build/libjpeg.a -o /tmp/luma-idct-modular-check
/tmp/luma-idct-modular-check

g++ -O3 -mavx2 -DINTEGER_PASS_BITS=3 -DNDEBUG -std=c++17 \
  -I/tmp/luma-idct-build -Isrc test/luma-idct.cc \
  /tmp/luma-idct-build/libjpeg.a -o /tmp/luma-idct-arithmetic-bench
taskset -c 0 /tmp/luma-idct-arithmetic-bench path/to/frame.jpg
IDCT_REVERSE_ORDER=1 taskset -c 0 /tmp/luma-idct-arithmetic-bench path/to/frame.jpg
```

Variant indices for TEST_ARITHMETIC and the fallback-count array are:
0 comp-control, 1 root-3over2, 2 root-45over32, 3 rotation-1-3over8,
4 root-and-rotation, 5 modular, 6 root-91over64, 7 root-181over128.

Raw data: `luma-idct-arithmetic-q{2,3,4}[-reverse]-results.jsonl` and
`luma-idct-arithmetic-q2-uncompensated-results.jsonl`. The latter disables
compensation; earlier B=2,3 records omit the later-added compensation boolean
but use its default enabled setting. All files retain individual trials,
checksums, precision and per-variant fallback counts. The basis compensation
is data-independent; the measured quality/speed preferences are specific to
this limited camera cohort and machine. No full decode throughput is claimed.
