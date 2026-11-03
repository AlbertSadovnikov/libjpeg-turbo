# Expanded Y quantizer cache

> Historical PGO-assisted cohort. The user now requires no PGO in comparisons,
> with LTO allowed. Use [the matched LTO-only report](../lto-only/README.md) for
> current overall numbers and selection; the original evidence below is preserved.

Implements steps 1–3 of the agreed next plan. Baseline is the selected
register-rewritten paired Y + guarded inline AVX2 zeroing + retained entropy
PGO/ThinLTO + reduced fused UV pipeline. No production source changes.

**Decision: do not select this cache.** It preserves output but shows no
convincing whole-path benefit: mean NV12 latency is 1.78% higher, with four
of five brackets regressing. The identical-binary comparison is noisy too,
so this is an observed regression, not a universal 1.78% penalty.

## Change

`cache.h` compares the actual 64 signed IFAST multipliers once per fast-IDCT
frame. On change it copies a 128-byte snapshot and expands each row to a
32-byte vector containing identical 128-bit halves. It compares contents,
not table pointers, so address reuse and table replacement are supported.
Accurate IDCT and unsupported fusion configurations retain their old paths.

`cached.asm` replaces eight broadcasts plus register multiplies with eight
multiply memory operands. Coefficients and arithmetic order are unchanged.
The transform shrinks from 198 to 190 instructions. Cache snapshot/expanded
arrays need 128/256 bytes; flag/alignment make the complete cache 416 bytes.
Actual wrapper TLS context grows from 1,888 to 2,304 bytes. Quantizer operand
loads now read 256 rather than 128 bytes per pair; this can offset instruction
savings. No exact cache/bandwidth cost is attributed from instruction counts.

The whole NV12 timing includes table comparison, any expansion, and added
cache footprint. Direct kernel timing prepares the cache outside clocks and
therefore measures a different operation/working set.

## Validation

All 120 captures, both IDCT modes, six fixtures (`rst1`, `optimized`,
`progressive`, `dense`, `tail63`, `zeroac`), padded/unaligned output and unchanged
padding match the retained selected output reports. A mixed sequence alternates
original JPEGs, boundary fixtures, and two JPEGs with modified Y DQT values
while leaving entropy payloads unchanged. This exercises table changes and
return to previous values within one decoder/process.

The direct checker compares every captured frame-60 Y pair and 10,000
synthetic pairs against two upstream SSE2 IDCT calls. Each synthetic pair is
also checked with a random full-range signed multiplier table and a mutation
at the same pointer. Unchanged-table updates must return false. Arithmetic,
clipping, output column and padding match. No checker work is inside kernel
timing loops.

## Timing

| Five full-path brackets | Control | Candidate | Change | Improving |
|---|---:|---:|---:|---:|
| Expanded quantizer cache | 3.5142 ms | 3.5769 ms | +1.78% | 1/5 |
| Identical-binary noise control | 3.5572 ms | 3.5659 ms | +0.25% | 3/5 |

Cache changes range −0.27% to +5.04%; identical-code changes range −2.80% to
+3.15%. Preserve these large fluctuations; no fixed frequency or second CPU
was available. Do not compare absolute times with older experiment cohorts.
Each bracket is control/candidate/control on CPU 0, 90 preloaded held-out
frames, three passes after a full warmup. Candidate/noise order alternates.
All inputs, allocation and hashing are outside decode timers. Same codec
archives, controller clear and chroma source/flags across cases; only the
wrapper/cache and Y assembly change. No compiler profile is changed.

Direct kernel means are 21.38 ns/pair for register baseline and 21.67 for
cached, with one large outlier in the cached rounds. Captured pairs and output
reuse differ from full decode, so do not scale this difference into an exact
pipeline budget. Raw rounds are in `kernel.json` and `results.json`.

An initial cohort stopped after one valid bracket because the copied noise
control lacked execute permission. `interrupted-results.json` preserves it;
copying now preserves mode. The complete cohort was rerun without repeating
unchanged validation (`--timing-only`). No implementation changed.

## Reproduce

```
python3 test/webcam/nv12/quantizer-cache/build.py
python3 test/webcam/nv12/quantizer-cache/audit.py
python3 test/webcam/nv12/quantizer-cache/run.py
# A separate timing-only cohort must use separate output names if retained:
python3 test/webcam/nv12/quantizer-cache/run.py --timing-only
```

Requires retained previous experiments/capture/fixtures as documented in
`../NEXT_EXPERIMENTS.md`. Generated binaries, sources and changed-table JPEGs
stay in `/tmp/mjpeg-quantizer-cache`. Reviewable changes are `cache.h`,
`cached.asm` and `wrapper.patch`; JSON retains hashes, validation and raw rounds.
The preferred candidate stays unchanged, including inline zeroing.
