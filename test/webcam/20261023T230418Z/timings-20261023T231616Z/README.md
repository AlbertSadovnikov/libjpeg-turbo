# Webcam sequence decode timings

Preload complete sequence, reuse decoder and output, one full warmup pass per process; CLOCK_MONOTONIC per-frame timing; single pinned CPU; no disk/capture time. Stage timers use the separate WITH_PROFILE build.

120 frames, 3 trials x 3 measured passes; CPU 0.

| Configuration | Mean ms | Median ms | p95 ms | p99 ms | FPS |
|---|---:|---:|---:|---:|---:|
| bgr | 6.026 | 6.019 | 6.132 | 6.474 | 165.9 |
| lookahead10 | 6.045 | 6.034 | 6.191 | 6.683 | 165.4 |
| fast-upsample | 5.569 | 5.564 | 5.675 | 5.863 | 179.6 |
| fast-idct | 5.522 | 5.526 | 5.616 | 5.667 | 181.1 |
| half | 4.510 | 4.492 | 4.644 | 4.952 | 221.7 |
| gray | 4.208 | 4.213 | 4.299 | 4.338 | 237.6 |
| no-simd | 13.317 | 13.288 | 13.645 | 14.157 | 75.1 |
| profile | 10.059 | 10.037 | 10.428 | 10.653 | 99.4 |

Profile timings include instrumentation overhead and must not be treated as a decomposition of uninstrumented latency.

| Instrumented stage | Mean ms |
|---|---:|
| header_ms | 0.0022 |
| setup_ms | 0.0040 |
| entropy_ms | 3.4695 |
| idct_ms | 2.8173 |
| upsample_ms | 0.3657 |
| color_ms | 0.7139 |
| finish_ms | 0.0006 |

All 120 frames matched exactly without decoder warnings.
