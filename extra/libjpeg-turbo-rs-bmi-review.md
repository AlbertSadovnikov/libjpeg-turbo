# Clarification: the BMI/LZCNT benchmark quotation

Checked 2026-10-31. The quoted "Encoding — portable build" paragraph and
`experiments/portable_vs_native_x86_64_2026-09-08.md` belong to
https://github.com/developer0hye/libjpeg-turbo-rs, not imazen/zenjpeg.
Reference checkout: `/tmp/libjpeg-turbo-rs-reference`, revision
`b614c77936e56e6409c06af87fb104a5e75e64ee`.

`src/encode/huffman_encode.rs` explicitly dispatches the same AC encode body
between SSE2, BMI1+LZCNT, and BMI1+LZCNT+BMI2 target-feature entry points. The
writer selects its feature tier once; the block encoder then calls the tier.
The documented benefits are TZCNT/BLSR for walking nonzero coefficient masks,
leading-zero operations for bit lengths, and SHLX/SHRX for the inlined bit
packer. The BMI2 entry-point documentation explicitly attributes that win to
variable shifts rather than PEXT/PDEP. The cited benchmark measures encoding.
No corresponding baseline decoder BMI dispatch was found in the inspected
`src/decode/huffman.rs` and `src/decode/bitstream.rs` sources.

This does not mean those instructions cannot help decoding. SHRX/SHLX and BZHI
are candidates for the scalar decoder's bit extraction, masks and shifts.
Baseline decoding already obtains category/zero-run information from Huffman
symbols, so encoding's coefficient-mask traversal does not transfer directly.
Progressive refinement bitmap iteration is another case where TZCNT/BLSR can
help, but our webcam frames are baseline JPEGs.

Our earlier `test/webcam/bmi2` experiment enabled BMI1/BMI2 only for the
original jdhuff object. It generated SHLX, SHRX and BZHI but showed no
consistent full-sequence benefit. That predates the successful two-symbol
lookup and threshold changes: it does not settle BMI instruction selection
for the current winner. No new BMI benchmark was run as part of this source
clarification. These are scalar bit-manipulation instructions, distinct from
SIMD processing of independent data lanes.

The [subsequent current-decoder experiment](../test/webcam/bmi-current/README.md)
does find a benefit from BMI2 alone: 2.13% less accurate-NV12 decode time and
1.22% less fast-IDCT NV12 time across the 120-frame sequence, plus matching
outputs and isolated archive changes. BMI1/LZCNT and the combined tier do not
improve on BMI2 alone. The earlier no-gain result was specific to the old loop.
