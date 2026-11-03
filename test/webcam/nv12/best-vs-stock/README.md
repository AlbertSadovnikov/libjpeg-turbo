# Current best exact-fast NV12 versus stock: every captured resolution

Fresh fixed-build cohort on Ryzen 9 3900X, CPU 0. Baseline is stock fast JPEG→NV12. Candidates preserve the stock-fast NV12 output contract; no reduced-chroma approximation. All 174 control/candidate/control brackets match output hashes. Prior literal-output and padding validation remains in `multi-camera/` and `restart-segment/`.

Candidate selection was fixed before timing, not picked per resolution:

- Logitech Clang: paired exact fast path (`clang-camera-exact`).
- Logitech GCC: paired exact fast path plus deferred entropy loads (`gcc-camera-deferred`).
- LifeCam Clang: restart-segment controller (`clang-segment`).
- LifeCam GCC: isolated restart decoder (`gcc-tu-fast`); the slower new GCC segment packaging is not selected.

Same compiler for each baseline/candidate pair. O3, LTO core, no PGO, no explicit mtune/march/mcpu; established matched BMI2 entropy tier and native support. No production changes or new executable selections. All runs sequential; no build or validation competed with timing.

Each resolution uses twelve frames from its highest requested FPS capture mode. Three brackets, reversed case order in the middle round; `max(20, ceil(4000000 / pixels))` passes. Inputs are preloaded; file IO, allocation and hashing are outside decode timing. Every round is retained, including outliers. This covers every captured resolution, not every frame-rate mode. Different resolutions contain different scenes/exposures; these are decode timings, not measured camera arrival rates.

Cells show **stock → current best milliseconds per frame** and **percent less time**, computed as `100 × (1 − best / stock)`. Percent less time differs from percent higher throughput.

## Logitech C930e

| Resolution | Clang stock → best ms | Less time | GCC stock → best ms | Less time |
|---|---:|---:|---:|---:|
| 160x120 | 0.096 → 0.070 | 26.9% | 0.096 → 0.072 | 25.3% |
| 176x144 | 0.124 → 0.089 | 28.4% | 0.124 → 0.091 | 27.2% |
| 320x180 | 0.172 → 0.144 | 16.4% | 0.170 → 0.148 | 12.9% |
| 320x240 | 0.279 → 0.201 | 28.1% | 0.281 → 0.205 | 27.0% |
| 352x288 | 0.369 → 0.265 | 28.3% | 0.372 → 0.270 | 27.4% |
| 424x240 | 0.391 → 0.313 | 19.9% | 0.392 → 0.319 | 18.5% |
| 480x270 | 0.461 → 0.374 | 19.0% | 0.460 → 0.381 | 17.1% |
| 640x360 | 0.749 → 0.536 | 28.4% | 0.750 → 0.536 | 28.5% |
| 640x480 | 0.933 → 0.657 | 29.6% | 0.941 → 0.660 | 29.8% |
| 800x448 | 1.123 → 0.790 | 29.7% | 1.130 → 0.799 | 29.3% |
| 848x480 | 1.279 → 0.889 | 30.5% | 1.259 → 0.891 | 29.3% |
| 800x600 | 1.370 → 0.996 | 27.3% | 1.393 → 0.968 | 30.5% |
| 960x540 | 1.543 → 1.256 | 18.6% | 1.541 → 1.282 | 16.8% |
| 1024x576 | 1.656 → 1.173 | 29.1% | 1.657 → 1.183 | 28.6% |
| 1280x720 | 2.588 → 1.800 | 30.4% | 2.582 → 1.806 | 30.0% |
| 1600x896 | 3.773 → 2.603 | 31.0% | 3.848 → 2.728 | 29.1% |
| 1920x1080 | 5.072 → 3.515 | 30.7% | 5.087 → 3.497 | 31.3% |

## Microsoft LifeCam Studio

| Resolution | Clang stock → best ms | Less time | GCC stock → best ms | Less time |
|---|---:|---:|---:|---:|
| 160x120 | 0.131 → 0.099 | 24.3% | 0.134 → 0.100 | 25.5% |
| 176x144 | 0.182 → 0.134 | 26.7% | 0.189 → 0.139 | 26.4% |
| 320x240 | 0.436 → 0.311 | 28.6% | 0.452 → 0.319 | 29.6% |
| 352x288 | 0.604 → 0.423 | 29.9% | 0.627 → 0.434 | 30.8% |
| 432x240 | 0.610 → 0.434 | 28.8% | 0.632 → 0.461 | 27.1% |
| 640x360 | 1.300 → 0.925 | 28.8% | 1.332 → 0.914 | 31.4% |
| 640x480 | 1.222 → 0.834 | 31.7% | 1.263 → 0.853 | 32.4% |
| 800x448 | 1.731 → 1.207 | 30.3% | 1.794 → 1.247 | 30.5% |
| 800x600 | 2.324 → 1.636 | 29.6% | 2.428 → 1.632 | 32.8% |
| 960x544 | 2.675 → 1.820 | 31.9% | 2.764 → 1.889 | 31.7% |
| 1280x720 | 3.676 → 2.481 | 32.5% | 3.822 → 2.540 | 33.6% |
| 1920x1080 | 6.012 → 3.875 | 35.5% | 6.312 → 3.952 | 37.4% |

All means and every bracket improve against stock. Smaller gains at Logitech 320×180, 424×240, 480×270 and 960×540 include partial-MCU fallback; they are not excluded from this table. Unfixed clocks and occasional runtime outliers limit precision, especially for small differences. A second CPU and broader scenes remain untested.

## Evidence and reproduction

`protocol.json` records binary/archive/input hashes and choices. `results.json` contains every process and bracket. `summary.json` and `summary.csv` retain full precision, throughput and bracket ranges. These are a fresh cohort, not ratios synthesized from older timings.

```sh
python3 test/webcam/nv12/best-vs-stock/run.py
```

Requires the saved native binaries/archives referenced by the earlier experiments; see their build recipes. No clean-checkout standalone reconstruction is claimed.

## Later partial-MCU follow-up

The four partial-MCU Logitech rows above predate the new edge reconstruction.
[New exact-fast edge results](../partial-mcu/README.md) improve those workloads
with fresh stock and previous-fallback controls. Keep these historical numbers
separate; full-MCU/default selections remain unchanged.
