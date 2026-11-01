# Chroma latency budget after Huffman decode

1920x1080 4:2:2 webcam fixture, held-out frame 60 from the capture. Current
Clang 18 PGO+ThinLTO C decoder, Ryzen 9 3900X, CPU 0. No RGB conversion or GPU
work. Each of 16,200 MCUs has two Y blocks, one Cb block and one Cr block.

| Operation | Accurate IDCT | Share of full decode | Fast IDCT | Share |
|---|---:|---:|---:|---:|
| Full JPEG to NV12 | 4.240 ms | 100% | 3.871 ms | 100% |
| Cb+Cr IDCT, including dequantization and output stores | 0.785 ms | 18.5% | 0.588 ms | 15.2% |
| Vertical average + UV interleave, AVX2 | 0.032 ms | 0.76% | 0.032 ms | 0.83% |
| Chroma reconstruction + packing, approximate sum | 0.817 ms | 19.3% | 0.621 ms | 16.0% |

Chroma reconstruction plus packing is roughly 50 ns/MCU accurate and
38 ns/MCU fast. Cb and Cr each contribute one IDCT per MCU. Halving and
interleaving run together in the AVX2 packer, so they are not split into
independent latency numbers.

Coefficient zeroing, run expansion, DC prediction, sign extension and zigzag
stores are interleaved with Huffman decoding. There is no independent
post-Huffman coefficient-construction stage in the current decoder. Its
chroma-only share has not been isolated and is **not included** in the
reconstruction/packing sum above. Dequantization is included in IDCT.

## Optimization implications

Packing alone offers less than 1% of full latency on this frame. Chroma IDCT
is the larger post-entropy target. Halving that work would save roughly
9% of accurate decode or 7.6% of fast decode, before integration effects.
Parsing all chroma symbols remains necessary even if fewer output rows are
reconstructed.

Fusing chroma IDCT's output with vertical averaging and interleaving could
avoid intermediate U/V stores and reads. A transform producing fewer rows
could target arithmetic too, but standard scaled IDCT is not automatically
equivalent to averaging adjacent full-resolution, rounded/clipped samples.
Output-equivalence checks would be part of that experiment.

This frame has 32,400 chroma blocks and 82,560 nonzero AC coefficients:
2.55 AC values per chroma block on average. About 19.9% of chroma blocks
are DC-only. Existing SIMD IDCT routines already test for zero AC columns;
sparsity is not all an untapped opportunity.

## Method and limits

The driver captures quantized coefficients outside timing. Each component's
IDCT is batch-timed over a full plane. Cb+Cr are also timed together, avoiding
per-block clock reads. Full decode uses the actual raw-strip NV12 path.
Packing is timed on prepared full-resolution chroma planes. Each stage runs
for at least 0.2 seconds after warmup; results are medians of three runs.
Direct Y reconstruction and packed UV bytes are checked against full NV12
for both IDCT methods before timing.

These are stage estimates, not exact additive in-pipeline accounting: the
isolated IDCT streams predecoded coefficient planes, whereas normal decode
uses cache-hot reusable MCU buffers. Packing here streams full planes rather
than freshly reconstructed 8-row scratch strips. Cache behavior and dispatch
overhead differ. The percentages give an optimization budget, not an exact
promise of speedup from removing a stage. No production source was changed.

Run `python3 test/webcam/nv12/chroma-budget/run.py`. It requires the retained
PGO+ThinLTO build and Google Benchmark artifacts. `results.json` holds raw
runs, `summary.json` the normalized results, and `driver.cc` the measurement.
