# Persistent combined AC lookup experiment

The isolated decoder change is saved in [fused-ac.patch](fused-ac.patch).
It modifies `src/jdhuff.c` and the private `jpeg_decomp_master` structure in
`src/jpegint.h`. The decoder sources in the working checkout are unchanged.

For short AC tokens, one table lookup returns the zero run, signed amplitude,
and total number of consumed bits. Longer tokens use the existing decoder.
The lookup includes EOB and ZRL handling. The general MCU decoder, restart
handling, DC prediction, and progressive decoding remain in place.

Each AC table has a cache in the decoder's permanent memory pool. Its contents
are checked against the current Huffman table before reuse and rebuilt on a
change. The camera sequence builds two lookup tables once across all 120 frames.
The 10-bit version uses two 4 KiB lookup arrays plus cache metadata.

## Results

[Full results and per-frame CSVs](20261023T233210Z/README.md) were collected
on CPU 0 of the Ryzen 9 3900X. Each variant decoded all 120 preloaded frames
in five trials of three measured passes, with a complete warmup pass per process.
The decoder and output buffer were reused. Variant order was rotated.

| Variant | Mean ms/frame | Reduction from contemporary baseline |
|---|---:|---:|
| Baseline | 6.1077 | — |
| Combined 10-bit | 5.9938 | 1.86% |
| Combined 11-bit | 6.0196 | 1.44% |
| Combined 12-bit | 6.1084 | -0.01% |

The 10-bit version improved all five trial means, with reductions of
1.06–2.93%. This is a modest result from one recorded scene and one CPU.
These measurements have no low-level profiling instrumentation.

## Validation

- Every camera frame matches the baseline pixel-for-pixel for all three widths.
- Persistent-decoder output hashes match across Huffman table changes,
  geometry changes, progressive frames, and restart-marker frames.
- The persistent sequence checks cover BGR, grayscale, half-size output,
  fast upsampling, and fast IDCT.
- Trace assertions confirm two table builds for the entire camera sequence.
- All 332 existing CTest tests pass with the 10-bit build. The test log is
  saved with the results.

## Build and repeat

Apply the patch to a fresh copy of this checkout. This session's patched copy
is `/tmp/mjpeg-fused-src`. The cache changes private structure layout, so
rebuild the complete library and compile internal benchmark code against the
matching headers.

```sh
cmake -S /tmp/mjpeg-fused-src -B /tmp/mjpeg-fused10 \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_SHARED=OFF -DWITH_PROFILE=OFF \
  -DCMAKE_C_FLAGS=-DMJPEG_FUSED_BITS=10
cmake --build /tmp/mjpeg-fused10 -j 8
ctest --test-dir /tmp/mjpeg-fused10 --output-on-failure -j 8
```

For the other variants, replace `10` with `11` or `12` in the build directory
and compiler definition. The baseline is the unmodified Release build at
`/tmp/mjpeg-release`.

The comparison runner uses these session builds and the temporary JPEG
fixtures created during the earlier entropy investigation:

```sh
python3 test/webcam/fused-ac/run.py test/webcam/20261023T230418Z
```

`MJPEG_FUSED_TRACE=1` prints a line whenever a combined lookup table is rebuilt.
Tracing is disabled during performance measurements. This remains an
experimental patch; malformed-input fuzzing and broader performance coverage
have not been performed.
