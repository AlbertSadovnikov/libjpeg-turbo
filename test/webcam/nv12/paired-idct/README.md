# Paired Y-block fast IDCT

Two adjacent Y blocks within a 4:2:2 MCU are transformed together, one block per 128-bit lane of AVX2 registers. This is a prototype for the existing fused JPEG-to-NV12 path, not a change to production codec sources. Entropy decoding and chroma reconstruction remain unchanged.

The generator lifts upstream `simd/x86_64/jidctfst-sse2.asm` arithmetic into lane-local AVX2 operations. It preserves 16-bit wraparound, signed high multiplication, shifts, saturation and sample centering. Each quantizer row is broadcast to both lanes, coefficients are loaded from the two block pointers, and each output row is joined into a single 16-byte store. Input coefficient loads and output stores support unaligned addresses; the quantizer table retains the codec's alignment requirement. The initial version omits the sparse-column shortcut and executes the full transform in both lanes.

Only JDCT_IFAST uses the paired kernel. Accurate IDCT retains the existing calls. The existing fusion guard requires AVX2/FMA and checks the full-resolution raw YCbCr 4:2:2 layout, full MCU geometry and supported output configuration. This assembly uses the SysV x86-64 calling convention. No new CPU-independent default is proposed.

## Measurements

Ryzen 9 3900X, CPU 0, existing Clang PGO+ThinLTO codec archives and fused reduced-chroma kernel. Both controls and candidates use the same archives, driver, exact-chroma object and compiler flags; only the fusion wrapper's two Y calls change. The new assembly is not PGO trained. G++ compiles both wrappers with identical `-O3 -DNDEBUG -std=c++17 -mavx2 -mfma` options.

| End-to-end JPEG → NV12 | Existing Y IDCT | Paired Y IDCT | Latency change |
|---|---:|---:|---:|
| Initial five brackets | 3.661 ms | 3.578 ms | −2.28% |
| Confirmation five brackets | 3.642 ms | 3.558 ms | −2.31% |

Each bracket is control/candidate/control, with 90 preloaded held-out webcam frames, three measured passes after a full warmup. Each batch has four improving brackets and one regressing bracket; all observations are retained. The roughly 84 µs mean reduction repeats, but individual rounds are noisy. This is evidence on one CPU, not a cross-CPU result. These are full NV12 latencies, not isolated entropy timings.

The direct kernel test transforms 16,200 Y-block pairs extracted from embedded camera frame 60. Over five rounds (50 passes each), two existing SSE2 calls average about 40.0 ns per pair versus 22.0 ns for the paired kernel, approximately 45% lower. This hot, reused-destination microbenchmark does not predict the entire pipeline gain. Only 141 pairs have both blocks eligible for the upstream sparse-column shortcut; 597 have exactly one eligible block. Sparse images may behave differently.

## Validation

The complete existing NV12 validation report is identical between control and candidate on all 120 captured frames and six fixtures: restart interval 1, optimized Huffman tables, progressive, dense AC, coefficient 63 and zero AC. It covers both IDCT modes and padded output strides. The paired Y transform introduces no additional output error; the existing reduced-chroma approximation remains the same.

The direct test additionally compares every captured Y-block pair and 10,000 synthetic pairs against two upstream SSE2 calls, including DC-only, first-row-only and arbitrary full-range signed 16-bit coefficients. Output buffers use a nonzero column and padded stride; padding bytes must remain untouched. All bytes match. This does not establish support for every JPEG mode or malformed input.

## Reproduction

The scripts depend on retained local builds: `/tmp/mjpeg-fused-chroma` (driver, exact object, source headers and `pgo` archives), `/tmp/mjpeg-pgo-lto` (baseline and embedded-frame object), and `/tmp/mjpeg-google-bench`. Frame capture and fixture dependencies match the adjacent experiments. Generated assembly keeps the upstream copyright header.

```
python3 test/webcam/nv12/paired-idct/build.py
taskset -c 0 /tmp/mjpeg-paired-idct/check > test/webcam/nv12/paired-idct/kernel-summary.json
python3 test/webcam/nv12/paired-idct/run.py
python3 test/webcam/nv12/paired-idct/run.py --timing-only
```

`validation.json` stores complete output checks; `results.json` and `confirm-results.json` retain raw timings. Their corresponding summaries retain every bracket. `kernel-summary.json` records direct kernel timing and sparse-pair counts. `build.py` generates the assembly and both wrapper sources under the experiment/temp directory, links matched binaries, and records hashes in `artifact-summary.json`.

Next useful work is testing another CPU and sparse scenes, followed by removing avoidable packing/quantizer-load overhead if measurements support it. The current result is worth retaining as an experimental candidate.
