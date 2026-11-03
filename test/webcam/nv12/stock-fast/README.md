# Stock TurboJPEG fast IDCT, planar 4:2:2 to NV12

Unmodified production codec source, fresh GCC 13.3 Release build:
`-O3 -DNDEBUG`, normal runtime SIMD dispatch, no PGO/LTO or internal patches.
The only custom code is the application-side NV12 packer and benchmark driver.

The measured path is:

1. Reuse a `tj3Init(TJINIT_DECOMPRESS)` handle with `TJPARAM_FASTDCT=1`.
2. `tj3DecompressToYUVPlanes8()` writes Y directly into the final NV12 Y plane
   and writes native 4:2:2 Cb/Cr into reusable application buffers.
3. AVX2 averages adjacent chroma rows with unsigned rounded averaging, then
   interleaves Cb/Cr into the NV12 UV plane. No RGB conversion occurs.

## Results

Ryzen 9 3900X, CPU 0, 1920x1080 4:2:2 webcam capture:

| Path / stage | ms/frame |
|---|---:|
| Stock TurboJPEG fast planar decode | 4.43694 |
| AVX2 vertical halving + UV interleave | 0.03109 |
| **Complete stock JPEG to NV12** | **4.46803** |
| Retained optimized fused fast-Y/reduced-chroma path | 3.62642 |

The stock path is approximately 224 frames/s on one core. The retained fused
path takes 18.84% less time in this same-cohort comparison (18.54–19.13%
across all three brackets). This compares complete decode-to-NV12 workloads,
but the fused variant also includes the prior entropy/compiler optimizations
and its previously measured reduced-chroma output difference. It is not an
isolated measurement of fusion alone or a byte-identical quality comparison.

Three stock-fused-stock brackets, 90 preloaded held-out frames, three measured
passes after a complete warmup pass. Decoder handles, chroma buffers and NV12
destination are reused. Capture, loading, allocation, hashing, GPU upload and
encoding are excluded. CPU frequency was not fixed. One additional per-frame
clock read separates decode from packing; its cost is negligible relative to
these millisecond timings.

## Validation

All 120 frames: stock planar + AVX2 NV12 matches stock libjpeg raw-output
fast-IDCT + AVX2, and matches the scalar packing reference byte-for-byte.
Padded, unaligned Y/UV destination strides also match and preserve padding.
The driver checks the FASTDCT parameter and requires the AVX2 packer.
Only the JPEG-to-NV12 path was tested.

The fresh build comes directly from this repository's clean `src/` and `simd/`
trees. Build/archive hashes, compiler and source identity are recorded in
`build-summary.json`; validation in `validation.json`; all bracket records in
`results.json`; aggregates in `summary.json`.

## Reproduce

Requires the retained capture, Google Benchmark artifacts and fused comparison
binary from the previous experiment. No network dependency is fetched here.

```sh
cmake -S . -B /tmp/mjpeg-stock-nv12 -DCMAKE_C_COMPILER=gcc \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_SHARED=OFF \
  -DWITH_BENCHMARKS=OFF -DWITH_TESTS=OFF -DBUILD=20261024
cmake --build /tmp/mjpeg-stock-nv12 --target jpeg-static turbojpeg-static -j 6
python3 test/webcam/nv12/stock-fast/run.py
```

`driver.cc` shows the application-side public API path. There is no running
web application or application URL for these command-line benchmarks.
