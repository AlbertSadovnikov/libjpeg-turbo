# Entropy reader and lookup layout experiments

Median of per-run mean CPU times, single embedded frame; candidate order rotated; baseline brackets each round; no low-level profiling.

| Variant | BGR ms | BGR reduction | Entropy/store ms | Entropy reduction |
|---|---:|---:|---:|---:|
| baseline | 6.0123 | 0.00% | 3.1509 | 0.00% |
| bulk-once | 5.9844 | 0.46% | 3.1167 | 1.09% |

All variants passed 333 regression tests, pixel comparisons for all 120 camera frames, persistent-decoder checks in five modes, and guarded-source chunk-boundary checks.
