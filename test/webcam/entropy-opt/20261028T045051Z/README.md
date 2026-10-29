# Entropy reader and lookup layout experiments

Median of per-run mean CPU times, single embedded frame; candidate order rotated; baseline brackets each round; no low-level profiling.

| Variant | BGR ms | BGR reduction | Entropy/store ms | Entropy reduction |
|---|---:|---:|---:|---:|
| baseline | 6.0697 | 0.00% | 3.1732 | 0.00% |
| bulk-once | 6.0025 | 1.11% | 3.1252 | 1.51% |
| bulk-sse2 | 6.1140 | -0.73% | 3.1854 | -0.39% |

All variants passed 333 regression tests, pixel comparisons for all 120 camera frames, persistent-decoder checks in five modes, and guarded-source chunk-boundary checks.
