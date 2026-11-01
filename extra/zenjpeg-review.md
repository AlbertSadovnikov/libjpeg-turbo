# zenjpeg decoder source review

Inspected 2026-10-31. Isolated checkout: `/tmp/zenjpeg-reference`.
Upstream: https://github.com/imazen/zenjpeg
Revision: `762fa7128c2124b42cfa6e23b30024a688f5b7a3` (2026-10-30).
Package manifest version: 0.9.0. Source license declaration:
`AGPL-3.0-only OR LicenseRef-Imazen-Commercial`.
This is source inspection, not a zenjpeg speed measurement or code integration.

Follow-up: [isolated C experiments](../test/webcam/zenjpeg-ideas/README.md)
tested alignment, refill and DC-only dispatch ideas. None established a reliable
full-NV12 gain over our threshold-pair10 control on this frame/CPU. These do not
measure or rank the complete Rust decoder.

## Entropy decoding

Source: `zenjpeg/src/huffman/encode.rs`, `zenjpeg/src/entropy/decoder.rs`,
`zenjpeg/src/foundation/bitstream.rs` at the pinned revision.

The executable constant is **FAST_BITS=10**, despite numerous comments and
local variable names still referring to 9 bits / 512 entries. Both the regular
symbol lookup and optional fused AC table use 1,024 signed 16-bit entries,
2 KiB each. AC fusion combines **one** nonzero symbol with its amplitude and
sign extension: signed 8-bit value, 4-bit run, 4-bit total consumed length.
There is no two-symbol AC lookup in the baseline implementation inspected.
Our compact9 experiment tested the 9-bit version of this representation, not
this exact 10-bit configuration; our single10 control used wider entries.
Do not equate those results with a measured zenjpeg result.

Long-code fallback peeks 16 bits and compares against pre-shifted exclusive
maxcode thresholds. That is the idea already successfully tested in our
`threshold-pair10` prototype, not a new source of gain by itself.

The reader is a **left/MSB-aligned 64-bit reservoir**. Lookup at fixed width N
is a constant shift by `64-N`; consuming bits shifts the reservoir left and
decrements its count. Our reader instead advances the count and extracts bits
relative to that count. Moving the variable shift from peek to consume can
change the dependency chain, but is not automatically faster.

Refill below 32 bits tries an 8-byte load + SWAR FF detection when <=24 bits
remain. On clean input it consumes **5–8 complete bytes**, as fit. If the
8-byte check fails, it tries a **4-byte clean prefix** before bytewise stuffing
and marker handling. Our scalar reader appends a fixed six bytes from an
eight-byte load and goes directly to bytewise handling when its FF test fails.
These are separate testable differences: reservoir alignment, refill policy,
and the 4-byte fallback. Bounds checks in zenjpeg's safe slices also differ
from our hoisted per-MCU input budget.

Some public decoder methods batch checks/refills and use inline fixed-size
table references to avoid Rust bounds checks. Trace actual call sites rather
than assuming every method named `fast` is selected: the optimized ordinary
baseline loop uses `decode_block_into_natural`; the native-plane scanline
reader inspected uses `decode_block_into`. The rotate-based bit extraction
helper has no call sites in the source inspected.

## IDCT and streaming

Source: `zenjpeg/src/decode/parser/baseline_streaming.rs`,
`zenjpeg/src/decode/idct_int.rs`, `zenjpeg/src/decode/pipeline.rs`.

Ordinary baseline RGB decoding fuses entropy, dequantization, IDCT and output
within MCU-row strips rather than allocating a full coefficient image. Our
raw-strip NV12 pipeline already follows the corresponding bounded-storage
architecture, while skipping chroma upsampling and RGB conversion.

Entropy returns coefficient extent / AC-presence information. The streaming
loop uses `coeff_count <= 1` to dispatch directly to a DC-only IDCT, avoiding
full dequantization and coefficient rescans. Libjpeg-turbo already has SIMD
zero-column shortcuts (`simd/x86_64/jidctint-avx2.asm`); the possible difference
is passing known sparsity from entropy, not inventing DC-only reconstruction.

On our actual embedded JPEG, independently reading quantized coefficients
with the original library gives:

| Component | Blocks | DC-only blocks | Share |
|---|---:|---:|---:|
| Y | 32,400 | 492 | 1.52% |
| Cb | 16,200 | 2,850 | 17.59% |
| Cr | 16,200 | 3,601 | 22.23% |
| Total | 64,800 | 6,943 | 10.71% |

DC-only includes all-zero blocks (Y 0, Cb 44, Cr 27). These counts suggest
testing coefficient-aware dispatch, especially for chroma, but do not measure
its benefit or account for the cost of tracking and transferring flags.

The default accurate IDCT is libjpeg-compatible 13-bit Loeffler, and its
AVX2 i16/pmaddwd path is explicitly a port of libjpeg-turbo's NASM algorithm,
including fused dequantization and wrap semantics. Do not assume it is an
independently faster algorithm. The alternative `IdctMethod::Jpegli` is a
12-bit stb/zune-derived integer transform, not C++ jpegli's float decoder and
not libjpeg's `JDCT_IFAST`; quality needs independent comparison.

Comments mention smart coefficient clearing, but the inspected natural-order
baseline hot path clears the whole 64-element buffer when clearing is needed.
It does not justify claiming a new partial-zeroing optimization. A scalar
4x4 sparse-IDCT kernel exists, but its tiered dispatcher explicitly uses the
full SIMD kernel for non-DC blocks because the scalar shortcut was slower.

## Native YUV / NV12 relevance

`ScanlineReader::read_rows_ycbcr_native_i16` exposes native-subsampled Y, Cb,
Cr with independent strides, without an RGB round trip. The public output is
**i16 planes**, not 8-bit NV12, so an adapter must pack samples, vertically
filter 4:2:2 chroma and interleave UV for our target.

The sequential native-plane method calls `decode_mcu_row`, which also performs
`strip.upsample_chroma()` before copying out native planes; those upsampled
results are unused by this read. It also copies strip data into caller planes.
A fair NV12 benchmark must account for that API overhead rather than compare
an arbitrary RGB decode or claim it writes final NV12 directly. No direct
NV12 output entry point was found in the decoder source inspected.

Restart-segment fused parallel entropy decoding requires a nonzero interval
and enough restart segments. Our frames have DRI=0 and no RST markers, so this
parallel entropy path cannot apply. This does not preclude parallel IDCT after
serial entropy or processing independent MJPEG frames on separate threads.
Progressive replay/bitmap optimizations target progressive JPEG, not our
baseline webcam stream.

## Candidate experiment order

1. Keep our successful two-symbol LUT and pre-shifted thresholds as controls.
2. Test MSB-aligned reservoir independently of refill policy.
3. Test 4-byte clean-prefix fallback and/or variable 5–8-byte refill separately.
4. Test entropy-known DC-only dispatch, measuring its flag/branch overhead.
5. If comparing zenjpeg end-to-end, use native planes, include required NV12
   packing, match the accurate IDCT contract, and report any remaining copies
   or unused upsampling. No timing claim is established by this review.
