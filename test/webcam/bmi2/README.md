# Huffman-only BMI1/BMI2 experiment

The measured change enables `-mbmi -mbmi2` only for `src/jdhuff.c`.
The [CMake patch](source-options.patch) is applied to the isolated source copy
at `/tmp/mjpeg-bmi2-src`; the build is `/tmp/mjpeg-bmi2`.

The [completed comparison](20261023T235010Z/README.md) used all 120 captured
1920 x 1080 webcam frames, with five trials of three measured passes per build
(1,800 timed decodes per build). Each process preloaded the entire sequence,
decoded one full warmup pass, reused its decoder and output buffer, and ran on
CPU 0. Build order alternated. Capture and disk I/O were excluded.

| Build | Mean ms/frame | Median ms/frame | p95 ms/frame |
|---|---:|---:|---:|
| Generic baseline | 6.0863 | 6.0645 | 6.2609 |
| Huffman-only BMI1/BMI2 | 6.1018 | 6.0592 | 6.4234 |

The BMI build was 0.25% slower on average. Two trial means improved and three
regressed, so this experiment shows no consistent performance benefit.

The Huffman object's disassembly contains 20 SHLX, 18 SHRX, and one BZHI
instruction. The baseline contains none of the checked BMI bit instructions.
These are static instruction counts, not execution counts.

## Isolation and validation

The comparison archives were made by copying each original baseline archive
and replacing only `jdhuff.c.o` with its BMI-compiled version. Every other
archive member was verified byte-for-byte identical. This avoids source-path
metadata differences introduced by rebuilding NASM objects in a different
source directory. Copies of the exact comparison archives are saved with
the results.

All 120 camera frames match pixel-for-pixel. Persistent-decoder output hashes
also match across a mixed sequence, with checks for BGR, grayscale, half-size
output, fast upsampling, and fast IDCT. The complete BMI CMake build passed all
332 existing CTest tests; its log is saved as `ctest.log` and copied into the
completed comparison directory.

This result concerns compiler-generated BMI instructions on the Ryzen 9 3900X.
Explicit extraction intrinsics or a redesigned bulk bit reader remain separate,
unmeasured changes.

## Repeat

Apply `source-options.patch` to a fresh source copy, then build and test:

```sh
cmake -S /tmp/mjpeg-bmi2-src -B /tmp/mjpeg-bmi2 \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_SHARED=OFF -DWITH_PROFILE=OFF
cmake --build /tmp/mjpeg-bmi2 -j 8
ctest --test-dir /tmp/mjpeg-bmi2 --output-on-failure -j 8
python3 test/webcam/bmi2/run.py test/webcam/20261023T230418Z
```

The runner expects the original generic build at `/tmp/mjpeg-release` and
the BMI build above. It saves assembly, per-frame timing CSVs, summary JSON,
commands, comparison archives, and benchmark binaries in a new timestamped
directory.
