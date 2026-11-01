# PGO and LTO: JPEG to NV12

Ryzen 9 3900X, GCC 13.3 and Clang 18.1.3. Same threshold-pair10 C decoder
source throughout; no receive assembly patch. GCC baseline: `-O3 -DNDEBUG`.
Clang baseline adds `-mtune=znver2`. Both enable BMI2 on jdhuff.c only.

PGO trains on the first 30 captured frames, using the actual NV12 strip
decoder with both accurate and fast IDCT. The remaining 90 frames are held
out for measurement. They are from the same capture, so scene generalization
is not established. PGO+LTO gets its own instrumented training build.

| Compiler | Optimization | Accurate NV12 ms | Fast NV12 ms |
|---|---|---:|---:|
| GCC | Baseline | 4.3998 | 3.9823 |
| GCC | LTO | 4.4637 | 4.0444 |
| GCC | PGO | 4.3438 | 3.9526 |
| GCC | PGO + LTO | 4.3903 | 3.9826 |
| Clang | Baseline | 4.4055 | 3.9517 |
| Clang | ThinLTO | 4.3843 | 3.9920 |
| Clang | PGO | 4.2723 | 3.8781 |
| Clang | PGO + ThinLTO | **4.2435** | **3.8296** |

Clang PGO+ThinLTO reduces accurate time 3.68% and fast time 3.09% versus
its own baseline. GCC PGO reduces time 1.27% / 0.75%; LTO does not add a
consistent benefit there. These are matrix-screening results from three
rotated/reversed rounds, not bracketed final-candidate confirmation.

Each process preloads all 90 held-out frames, runs one complete warmup pass,
then three measured passes. CPU 0. Loading, allocation and output hashing
are outside decode timers. Every build and round produces matching NV12
hashes within each IDCT mode. Accurate versus fast IDCT remains a separate
quality choice.

The measurement C++ driver is compiled once with GCC, without PGO or LTO,
and the same native object is linked to every codec variant. Only codec C
objects participate in PGO/LTO; NASM IDCT routines keep their existing
implementation. All benchmark binaries use gold, including controls, to
avoid changing linkers only for LTO. GCC uses `-flto`; Clang uses
`-flto=thin`. Full profile-use flags are also passed at the final benchmark
link. This measures static-library LTO, without LTO into the C++ driver.

Profiles are kept under `/tmp/mjpeg-pgo-lto`. GCC uses
`-fprofile-prefix-path` to map generation/use build paths consistently.
Clang uses instrumentation profiles merged with llvm-profdata-18.
The hot libjpeg Huffman profiles are populated; GCC's missing-profile
diagnostics include untrained utility/TurboJPEG object copies. The NV12
path links libjpeg.a first and uses the profiled libjpeg implementation.

Validation and measurement scope here is JPEG-to-NV12, not other codec or
image-tool paths. Production sources/build settings are unchanged.

Reproduce with retained source/control/Google Benchmark prerequisites:

```sh
python3 test/webcam/bmi-intrinsics/pgo-lto/build.py
python3 test/webcam/bmi-intrinsics/pgo-lto/run.py
```

`build.py --resume` resumes completed preparation. `build-summary.json`
retains exact flags, training split, profiles and build history;
`summary.json` holds the NV12 results and benchmark binary hashes;
`results.json` retains all individual rounds. Scripts prepare codec libraries
and NV12 drivers only.
