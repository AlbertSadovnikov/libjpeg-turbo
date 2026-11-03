# Skip exactly zero reduced-chroma groups

Retained for the existing reduced-UV output contract. For each horizontal
half, inspect coefficients from both Cb and Cr at vertical frequencies 5–7.
Skip that contribution group only when every input is zero. All nonzero FMAs,
rounding and clipping retain their previous order. This introduces no further
quality loss: the entire previous NV12 output is preserved.

## Separate confirmation against previous selected reduced path

| Compiler | Control | Candidate | Time reduction |
|---|---:|---:|---:|
| clang | 3.3984 ms | 3.2511 ms | 4.33% |
| gcc | 3.5761 ms | 3.4366 ms | 3.90% |

Three control/candidate/control brackets, six passes, 90 preloaded frames,
CPU 0 on Ryzen 9 3900X. Every bracket improved. Initial five-bracket results
were 4.20% faster with Clang and 3.85% with GCC, again all improving.
Matched O3/LTO, no PGO, no explicit mtune/march/mcpu; BMI2 entropy and shared
native support unchanged. Raw evidence is in `../next-round/cd-*.json` and
`../next-round/confirm-*.json`. Identical-binary noise controls are retained.

All 120 captures, both IDCT methods, six boundary fixtures and mixed streams
preserve the control's full output reports and padding. Direct tests compare
16,200 captured pairs plus 20,000 synthetic cases and 20,000 changing
quantizers, including sparse/dense, full-range and low-amplitude rounding
stress. `kernel.json` and `../next-round/cd-validation.json` retain evidence.

In the capture, all frequency-5–7 inputs are zero for about 99.31% of lower
halves and essentially all upper halves. On the zero-AC fixture, end-to-end
reductions are approximately 8–9%. Dense inputs skip no groups: Clang changes
are within noise, while GCC improves about 9%. The latter cannot be attributed
to zero skipping: splitting the loop also changes compiler scheduling/layout.
These fixtures are synthetic, and one capture scene does not establish a
universal improvement.

```
python3 test/webcam/nv12/chroma-zero-groups/build.py
python3 test/webcam/nv12/chroma-zero-groups/check.py
python3 test/webcam/nv12/next-round/run-cd.py
taskset -c 0 /tmp/mjpeg-chroma-zero-groups/nv12 fast 2 6 JPEG...
```

`../next-round/selections.json` records the selected Clang binary and mode 2.
Stock-fast-exact mode 3 remains a separate candidate. No rejected entropy
control-word change is included. Inline AVX2 clearing and production src/simd
remain unchanged.
