# All captured resolutions: fixed-build decode comparison

Started 2026-11-03T12:26:34Z. All 29 camera/resolution groups, Clang and GCC; 174 control/candidate/control brackets, 522 sequential processes. Output hashes agree in every bracket.

Comparison: previous isolated restart-aware executable (`restart-tu`, control) versus the new segment executable with `MJPEG_SEGMENT=1`. This is **not a stock-decoder comparison**. Full stock-fast-exact NV12, mode `fast 3`; same Ryzen 9 3900X, CPU 0, no PGO or explicit CPU tuning, LTO core. No compilation or other validation ran during timing. Existing executable hashes were verified before running. Builds and selections are unchanged.

Each resolution uses twelve captured frames from its highest requested FPS mode. This covers every captured resolution, not every frame-rate mode. The files are preloaded by the driver; allocation/hashing stay outside decode timing. Three brackets per case, reversing case order in the middle round. Passes are `max(20, ceil(4000000 / pixels))` to lengthen small-image measurements. FPS, where exported, is CPU decode throughput, not camera capture FPS.

Times below are milliseconds per frame, averaged across brackets; negative change is faster. Bracket ranges expose variation rather than establish statistical confidence. Different resolutions have different captured content, so timing need not increase monotonically with pixel count.

## Logitech Webcam C930e

Logitech inputs have DRI 0; the segment controller is not installed. Differences here reflect packaging/layout and runtime variability, not segment-loop work reduction.

| Resolution | Clang control → segment ms | Change | Bracket range | GCC control → segment ms | Change | Bracket range |
|---|---:|---:|---:|---:|---:|---:|
| 160x120 | 0.0695 → 0.0693 | -0.31% | -0.67…-0.05% | 0.0708 → 0.0713 | +0.73% | +0.62…+0.83% |
| 176x144 | 0.0887 → 0.0882 | -0.63% | -1.35…-0.14% | 0.0902 → 0.0905 | +0.30% | +0.10…+0.64% |
| 320x180 | 0.1433 → 0.1422 | -0.77% | -1.57…-0.22% | 0.1472 → 0.1454 | -1.21% | -1.65…-0.71% |
| 320x240 | 0.2001 → 0.1985 | -0.76% | -1.19…+0.10% | 0.2028 → 0.2047 | +0.96% | +0.54…+1.53% |
| 352x288 | 0.2638 → 0.2614 | -0.90% | -1.42…-0.07% | 0.2673 → 0.2711 | +1.44% | +0.87…+1.76% |
| 424x240 | 0.3124 → 0.3095 | -0.92% | -1.60…-0.44% | 0.3215 → 0.3170 | -1.38% | -1.80…-1.08% |
| 480x270 | 0.3736 → 0.3691 | -1.20% | -1.54…-0.92% | 0.3843 → 0.3816 | -0.71% | -1.09…-0.06% |
| 640x360 | 0.5309 → 0.5287 | -0.43% | -1.18…+0.27% | 0.5377 → 0.5465 | +1.65% | +0.73…+2.44% |
| 640x480 | 0.6543 → 0.6507 | -0.55% | -1.01…-0.31% | 0.6597 → 0.6711 | +1.73% | +1.53…+2.02% |
| 800x448 | 0.7919 → 0.7821 | -1.23% | -1.45…-0.94% | 0.7977 → 0.8100 | +1.53% | +0.74…+2.15% |
| 848x480 | 0.8781 → 0.8705 | -0.86% | -1.52…-0.38% | 0.8869 → 0.9004 | +1.53% | +0.74…+2.14% |
| 800x600 | 0.9572 → 0.9510 | -0.65% | -1.77…+0.09% | 0.9757 → 0.9863 | +1.08% | -1.04…+2.56% |
| 960x540 | 1.2745 → 1.2527 | -1.71% | -4.23…-0.34% | 1.2921 → 1.2808 | -0.88% | -1.56…+0.14% |
| 1024x576 | 1.1578 → 1.1477 | -0.87% | -1.34…-0.36% | 1.1677 → 1.1902 | +1.93% | +1.80…+2.04% |
| 1280x720 | 1.7927 → 1.7656 | -1.51% | -1.69…-1.22% | 1.7942 → 1.8294 | +1.96% | +1.87…+2.03% |
| 1600x896 | 2.5805 → 2.5649 | -0.60% | -1.31…+0.55% | 2.5888 → 2.6517 | +2.43% | +1.60…+3.25% |
| 1920x1080 | 3.4365 → 3.4331 | -0.10% | -1.22…+1.17% | 3.4636 → 3.5209 | +1.66% | +0.96…+2.30% |

## Microsoft® LifeCam Studio(TM):

The structural segment guard is eligible for these LifeCam inputs.

| Resolution | Clang control → segment ms | Change | Bracket range | GCC control → segment ms | Change | Bracket range |
|---|---:|---:|---:|---:|---:|---:|
| 160x120 | 0.1008 → 0.0974 | -3.37% | -3.92…-2.65% | 0.0997 → 0.0996 | -0.17% | -0.84…+0.31% |
| 176x144 | 0.1373 → 0.1337 | -2.63% | -3.02…-2.38% | 0.1389 → 0.1370 | -1.37% | -3.67…+0.35% |
| 320x240 | 0.3170 → 0.3095 | -2.38% | -2.94…-1.80% | 0.3138 → 0.3122 | -0.51% | -1.04…+0.18% |
| 352x288 | 0.4346 → 0.4240 | -2.44% | -3.42…-1.80% | 0.4312 → 0.4288 | -0.55% | -1.62…+0.23% |
| 432x240 | 0.4448 → 0.4345 | -2.31% | -3.37…-0.67% | 0.4417 → 0.4408 | -0.21% | -0.39…-0.06% |
| 640x360 | 0.9156 → 0.8924 | -2.53% | -2.85…-2.21% | 0.9102 → 0.9075 | -0.30% | -1.87…+1.66% |
| 640x480 | 0.8575 → 0.8335 | -2.79% | -3.23…-2.13% | 0.8573 → 0.8468 | -1.23% | -2.14…-0.68% |
| 800x448 | 1.2364 → 1.2052 | -2.53% | -2.99…-1.83% | 1.2302 → 1.2296 | -0.05% | -0.41…+0.23% |
| 800x600 | 1.6476 → 1.5884 | -3.59% | -4.72…-2.31% | 1.6278 → 1.6196 | -0.50% | -1.66…+0.48% |
| 960x544 | 1.8643 → 1.8193 | -2.42% | -2.93…-2.15% | 1.8790 → 1.8627 | -0.87% | -1.52…-0.17% |
| 1280x720 | 2.5575 → 2.4764 | -3.17% | -3.53…-2.81% | 2.5185 → 2.5261 | +0.30% | -1.65…+1.42% |
| 1920x1080 | 3.9917 → 3.8538 | -3.45% | -3.86…-2.80% | 3.9169 → 3.9232 | +0.16% | -0.03…+0.50% |

## Interpretation

Clang improves all twelve LifeCam resolution means by 2.31–3.59%, with every individual bracket improving. GCC LifeCam means range from -1.37% to +0.30%; several brackets cross zero, so small means should not be treated as reliable gains.

This supports keeping the separate Clang restart candidate and the previous GCC selection. Logitech results do not establish a universal no-regression guarantee. The prior longer 1080p confirmation remains separately recorded; this sweep is a new cohort and does not replace or pool with it. No further tuning or default change was made.

## Evidence

`all-resolutions-protocol.json` records input/binary hashes and protocol; `all-resolutions-results.json` retains every process and bracket; `all-resolutions-summary.json` and `.csv` contain the complete numerical table. Reproduce sequentially with:

```sh
python3 test/webcam/nv12/restart-segment/all-resolutions.py
```
