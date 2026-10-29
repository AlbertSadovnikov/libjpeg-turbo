# Huffman-only BMI1/BMI2 experiment

Only `jdhuff.c.o` differs in each library archive. All other object files match byte-for-byte.

120 preloaded frames; 5 trials x 3 measured passes; CPU 0; one full warmup pass per process; reused decoder and output; alternating build order.

| Build | Mean ms | Median ms | p95 ms | p99 ms |
|---|---:|---:|---:|---:|
| release | 6.0863 | 6.0645 | 6.2609 | 6.5733 |
| bmi2 | 6.1018 | 6.0592 | 6.4234 | 6.7764 |

Mean time reduction: -0.25%.

All camera frames match pixel-for-pixel. Persistent-decoder checks pass for five output configurations and mixed encodings.

All 332 existing CTest tests pass; see `ctest.log`. The 0.25% mean regression is inconsistent across trials (two faster, three slower), with nearly identical medians. This experiment shows no consistent benefit from enabling compiler-generated BMI1/BMI2 instructions alone.
