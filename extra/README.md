# External reference: stb_image

`stb_image.h` v2.30 was downloaded on 2026-10-31 from:

https://raw.githubusercontent.com/nothings/stb/master/stb_image.h

SHA-256: `594c2fe35d49488b4382dbfaec8f98366defca819d916ac95becf3e75f4200b3`.
The header includes its upstream license options. It is not linked into the
codec or benchmark targets; it is retained for implementation comparison.

JPEG entropy observations:

- `FAST_BITS=9`. A 512-entry `int16` fast-AC table uses 1 KiB per AC table.
- `stbi__build_fast_ac` combines one nonzero AC symbol and its amplitude bits.
  An entry packs the signed amplitude into the upper byte, zero run into the
  next four bits and total consumed bits into the bottom four bits. It accepts
  amplitudes -128..127 when code plus amplitude fits within nine bits.
  Zero entries fall back; EOB and ZRL are handled by that path.
- This is single-symbol/value fusion, not two-symbol decoding. Our earlier
  fused-AC experiment uses the same broad idea; the winning two-symbol variant
  uses a wider 10-bit index and eight-byte entries (8 KiB per table).
- The ordinary fast Huffman lookup contains a symbol index, followed by separate
  length/value arrays. The upstream comment says repacking into an array of
  structs caused a 10% slowdown in the author's experiment; that is not a
  measurement on our CPU or workload.
- Long-code fallback compares the next 16 bits against pre-shifted `maxcode`
  thresholds. Code length is found without shifting the candidate each time.
- A left-aligned 32-bit reservoir is refilled byte by byte, with FF stuffing
  and markers handled in the refill routine. It is not a bulk/SIMD bit reader.
- Baseline decoding multiplies coefficients by their quantizers while storing
  them. Our libjpeg-turbo IDCT path performs dequantization in the IDCT kernel;
  moving this boundary requires a matched IDCT implementation and is not a
  drop-in entropy-only change.

The [stb-inspired experiments](../test/webcam/stb-entropy/README.md) now measure
compact single/pair entries and pre-shifted thresholds. Compact representations
regressed. The threshold variant reduced full NV12 hardware cycles by 1.36%
(accurate IDCT) and 3.04% (fast IDCT) in a separate five-pair confirmation.
Direct stb native-plane decode to NV12 took 8.35 ms versus pair10's 4.47 ms in
the main run, with small IDCT rounding differences. No dequantization-boundary
change was attempted. These are one-fixture/CPU results, not general rankings.
