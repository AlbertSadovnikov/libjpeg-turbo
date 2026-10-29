# Embedded-frame MJPEG benchmarks

Build the optional `mjpeg-bench` executable using Google Benchmark v1.10.0,
downloaded through CMake FetchContent with a pinned SHA-256 checksum:

```sh
cmake -S . -B /tmp/mjpeg-google-bench \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_SHARED=OFF -DWITH_BENCHMARKS=ON
cmake --build /tmp/mjpeg-google-bench --target mjpeg-bench -j 8
/tmp/mjpeg-google-bench/benchmarks/mjpeg-bench --benchmark_list_tests
```

`WITH_BENCHMARKS` defaults to OFF. Normal builds do not require C++, fetch any
benchmark dependencies, or embed the frame. The benchmark requires
`ENABLE_STATIC=ON` and `WITH_TURBOJPEG=ON` because it uses private codec
interfaces as well as both public APIs. C++17 is enabled only for benchmarks.
Google Benchmark's own tests and installation are disabled.

For an offline build, supply an unpacked Google Benchmark source tree with
`-DFETCHCONTENT_SOURCE_DIR_GOOGLEBENCHMARK=/path/to/benchmark`.

The [fixture](data/README.md) is compiled into the executable as a constant byte
array. Build-time generation uses CMake only, with no Python, xxd, objcopy, or
platform-specific linker requirements. There is no runtime frame loading.
Use `-DMJPEG_BENCHMARK_FRAME=/absolute/path/frame.jpg` to embed another fixture.
Stage validation requires an interleaved, 8-bit sequential YCbCr JPEG with three
components, Huffman coding, and no restart interval.

## Run

```sh
taskset -c 0 /tmp/mjpeg-google-bench/benchmarks/mjpeg-bench \
  --benchmark_min_time=1s --benchmark_min_warmup_time=0.2 \
  --benchmark_repetitions=5 --benchmark_enable_random_interleaving=true \
  --benchmark_out=/tmp/mjpeg-google-bench/results.json \
  --benchmark_out_format=json
```

`taskset` is optional and Linux-specific. Choose a CPU available to your process.
Filters select groups, for example `--benchmark_filter='MJPEG/Stages/Entropy'`
or `--benchmark_filter='BGR_Reused'`. Most results use milliseconds per complete
frame; setup microbenchmarks use microseconds. `items_per_second` is frames/s
for frame benchmarks, and `MPix/s` reflects output resolution. Byte throughput
uses compressed JPEG bytes, not output-buffer bandwidth, and is omitted for
stages that consume coefficients or pixel planes rather than JPEG data.

## Cases

There are 32 benchmarks:

- **Libjpeg and TurboJPEG full decodes:** BGR with reused or fresh decoders;
  fast upsampling; fast IDCT; both fast options; grayscale; BGRA; and BGR at
  1/2, 1/4, and 1/8 resolution. Destination buffers are allocated and faulted in
  before timing, including the fresh-decoder cases. Fresh-decoder timings
  include decoder creation/destruction and per-frame configuration.
- **Lifetime and setup:** create/destroy, header parsing plus abort/cleanup,
  decompressor startup alone, and rebuilding derived Huffman tables in reused
  storage. Startup excludes header parsing and cleanup using paused timing.
- **Coefficient API:** `jpeg_read_coefficients()` including header parsing,
  coefficient-image allocation, and finish/cleanup. This is not a pure entropy
  benchmark.
- **Entropy:** parse every MCU with coefficient stores and required zeroing,
  or discard coefficient output. Header parsing, startup, and cleanup are
  excluded. The discard path omits AC sign conversion/stores and does not
  exercise the same inner loop as producing coefficients. Neither case runs
  IDCT. The store case uses the small reusable MCU buffer, like normal decoding.
- **IDCT:** accurate and fast reconstruction of all actual coefficient blocks
  into full component planes. Coefficients and multiplier tables are prepared
  before timing. This reads a predecoded coefficient image, unlike the
  interleaved entropy/IDCT path's small hot MCU buffer.
- **Planar output:** JPEG to native subsampled YUV, and prepared YUV to BGR.
  TurboJPEG's YUV conversion API always uses box upsampling; this includes
  chroma expansion and color conversion, with entropy decoding and IDCT excluded.
- **Color conversion only:** full-resolution YCbCr planes, prepared with smooth
  upsampling before timing, converted to BGR without entropy decoding, IDCT,
  or upsampling in the timed region.

Before running, the executable verifies libjpeg/TurboJPEG pixel equality,
compares entropy output against `jpeg_read_coefficients()`, checks accurate and
fast IDCT planes against planar TurboJPEG output, and checks the YUV-to-BGR
path. Benchmark exceptions cause a nonzero exit status. With `WITH_TESTS=ON`,
`ctest --test-dir /tmp/mjpeg-google-bench -R mjpeg-bench-smoke --output-on-failure`
runs every case briefly, including these validation checks.

## Interpretation

These are repeated decodes of **one hot frame**, not the earlier 120-frame
sequence replay. Do not compare tiny differences across those workloads.
Stage timings are not additive: standalone stages have different buffering,
cache behavior, and call overhead. Full-frame benchmarks are the deciding
measurement for a proposed optimization.

Use Release builds and leave `WITH_PROFILE=OFF` for ordinary measurements.
Low-level profiling instrumentation adds substantial overhead. This suite does
not automatically apply the experimental fused-lookup or BMI patches; rebuild
the suite against each candidate library to compare it with the baseline.
