# NV12 error delta and per-MCU stage timings

2026-10-31, Ryzen 9 3900X, CPU 0, release builds, embedded 1920x1080 4:2:2
camera frame. The image has **120 x 135 = 16,200 MCUs**, each covering 16x8
luma pixels with **two Y blocks, one Cb block and one Cr block**: 64,800 blocks
per frame. NV12 output is 3,110,400 bytes, or 192 bytes per MCU on average.

## Error visualization

Run `render_delta.py` in a Python environment with NumPy and Matplotlib. For
this session:

```sh
/home/al/miniconda3/envs/segm/bin/python test/webcam/nv12/render_delta.py
```

The script compiles the pair10 NV12 driver, dumps accurate and fast NV12 via
`MJPEG_NV12_DUMP`, and writes these artifacts under `../error-delta/`:

- `overview.png`: accurate/fast previews, absolute display RGB difference x16,
  and signed native Y/U/V differences with labeled color bars.
- `crop.png`: a 128x128 crop selected by maximum luma absolute-error sum on a
  16-pixel grid. This is a high-error example, not an average region.
- `histograms.png`: signed sample-error distributions.
- `metrics.json`: exact signed histograms and sample-error statistics.

Signed error is **fast minus accurate**. Exact metrics are computed on native
NV12 samples; RGB previews use the same nearest-neighbor chroma expansion and
JPEG full-range display matrix for both images. Amplified RGB differences are
only a visualization, not the NV12 metric or ground-truth reconstruction error.

| Plane | Maximum absolute error | Mean absolute error | Mean signed error | PSNR against accurate |
|---|---:|---:|---:|---:|
| Y | 5 | 0.509260 | -0.489264 | 50.881 dB |
| U | 1 | 0.482242 | -0.482242 | 51.298 dB |
| V | 2 | 0.480905 | -0.480893 | 51.310 dB |

Most differences are a one-level downward shift. Only two Y samples differ by
five levels. About 99.0% of Y samples differ by at most one level. These are
differences between IDCT methods on this frame, not universal error bounds.

## Optimized decoder: stage measurements

Pair10 means scalar bulk refill plus the branchless two-AC-symbol LUT. Values
are **median of three per-run CPU means**. Each run measures full passes for
at least 0.3 s after 0.05 s warmup. Original/pair10 order alternates between
rounds. No per-MCU clock reads; `ns/MCU = measured frame ns / 16200`.

| Stage | Accurate ms/frame | Accurate ns/MCU | Fast ms/frame | Fast ns/MCU |
|---|---:|---:|---:|---:|
| Entropy + MCU coefficient zeroing/stores | 2.6877 | 165.91 | same stage | same stage |
| IDCT + dequantization, Y (2 blocks/MCU) | 0.8997 | 55.54 | 0.6306 | 38.92 |
| IDCT + dequantization, Cb (1 block/MCU) | 0.3986 | 24.61 | 0.3021 | 18.65 |
| IDCT + dequantization, Cr (1 block/MCU) | 0.3885 | 23.98 | 0.2949 | 18.21 |
| IDCT + dequantization, all planes, independently timed | 1.6966 | 104.73 | 1.2329 | 76.11 |
| Prepared chroma: vertical averaging + interleave, AVX2 | 0.0304 | 1.88 | same operation | same operation |
| Interleaved entropy + IDCT MCU pipeline | 4.4109 | 272.28 | 4.0524 | 250.15 |
| Full NV12, raw strips + AVX2, including setup/finish | 4.3983 | 271.50 | 4.0413 | 249.46 |
| Full NV12, planar + AVX2, including setup/finish | 4.3920 | 271.11 | 4.0762 | 251.62 |

Entropy is measured once: changing the downstream IDCT method does not change
the entropy stage. Both full paths are measured independently for each method.
Prepared chroma packing is also measured once, rather than claiming identical
timings for two separately measured outputs. Portable C packing is 0.0334
ms/frame, 2.06 ns/MCU. Header parsing plus abort is 0.710 microseconds/frame
(0.044 ns/MCU *amortized*, not an actual per-MCU operation). It is not complete
decoder startup, table construction, or normal finish cost.

## Original versus optimized controls

| Measurement | Original ns/MCU | Pair10 ns/MCU |
|---|---:|---:|
| Entropy, including zeroing/stores | 191.99 | 165.91 |
| Accurate IDCT, all planes | 106.05 | 104.73 |
| Fast IDCT, all planes | 76.06 | 76.11 |
| AVX2 chroma packing | 1.90 | 1.88 |
| Interleaved entropy + accurate IDCT | 299.55 | 272.28 |
| Full accurate NV12, raw strips | 313.71 | 271.50 |
| Full fast-IDCT NV12, raw strips | 280.30 | 249.46 |

The changes target entropy, not the IDCT or chroma kernels. Small variation in
unchanged stages reflects run conditions. Same-run controls are more useful
than comparing these numbers to earlier sessions with different clocks/load.

## Interpretation and limits

These are **frame-average costs**, not distributions of individual MCU latency:
coefficient sparsity and code lengths vary spatially. Stages are **not additive**.
Isolated IDCT reads a predecoded coefficient image in component order; the MCU
pipeline decodes into a small reusable buffer and processes blocks in MCU
order; full NV12 uses the library's scheduler and raw-row API. Output cache
behavior and loop/dispatch overhead differ. The pipeline can therefore take
slightly longer than a full decode without indicating a missing negative-cost
stage. Do not subtract them to infer exact setup or cache costs.

IDCT times include coefficient dequantization/multiplier use and reconstructed
sample stores; quantization-table setup is excluded. Entropy includes reservoir
refills, Huffman decode, sign extension, run handling, MCU zeroing and stores;
this run does not independently time each of those serial operations. Packing
includes 4:2:2-to-4:2:0 vertical averaging and Cb/Cr interleaving. No RGB
conversion, GPU transfer or encoder work occurs in the NV12 path.

The MCU pipeline's planes are validated against independent IDCT output for
both accurate/fast methods before timing, in original and optimized builds.
The extended benchmark smoke tests pass. No new per-MCU production profiling
instrumentation was introduced.

Reproduce: `python3 test/webcam/nv12/stages.py`. It requires the same temporary
builds and embedded object as `run.py`. Full records, trial ranges and exact
normalization are in `summary.json`; individual benchmark JSON/log files are
local generated artifacts. These results concern a repeatedly decoded single
frame, not the full 120-frame sequence or a GPU pipeline.
