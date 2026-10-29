# Entropy reader and lookup layout experiments

Median of per-run mean CPU times, single embedded frame; candidate order rotated; baseline brackets each round; no low-level profiling.

| Variant | BGR ms | BGR reduction | Entropy/store ms | Entropy reduction |
|---|---:|---:|---:|---:|
| baseline | 6.0179 | 0.00% | 3.1495 | 0.00% |
| bulk | 6.0280 | -0.17% | 3.2570 | -3.41% |
| compact | 5.9777 | 0.67% | 3.1939 | -1.41% |
| aligned | 6.0878 | -1.16% | 3.1905 | -1.30% |
| compact-aligned | 6.0995 | -1.36% | 3.1826 | -1.05% |
| bulk-compact-aligned | 6.1617 | -2.39% | 3.2839 | -4.27% |

All variants passed 333 regression tests, pixel comparisons for all 120 camera frames, persistent-decoder checks in five modes, and guarded-source chunk-boundary checks.
