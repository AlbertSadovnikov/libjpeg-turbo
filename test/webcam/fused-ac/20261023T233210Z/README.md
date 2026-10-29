# Persistent combined AC lookup experiment

Preloaded entire sequence; reused decoder/output; one full warmup pass per process; same CPU; rotated variant order; no instrumentation.

120 frames, 5 trials x 3 measured passes, CPU 0.

| Variant | Mean ms | Median ms | p95 ms | Time reduction |
|---|---:|---:|---:|---:|
| release | 6.1077 | 6.0976 | 6.4513 | 0.00% |
| fused10 | 5.9938 | 5.9824 | 6.1986 | 1.86% |
| fused11 | 6.0196 | 5.9946 | 6.3210 | 1.44% |
| fused12 | 6.1084 | 6.0722 | 6.4263 | -0.01% |

All three variants match every camera frame pixel-for-pixel. Persistent-decoder hashes match across table/geometry/progressive/restart transitions and five output configurations. Each variant builds only two AC tables across the 120-frame camera sequence.

All 332 existing CTest tests pass for the 10-bit build; see `ctest-10bit.log`. The 10-bit variant reduced time by 1.06–2.93% across the five trial means. The source patch and reproduction notes are in the parent directory.
