# Exact-fast fused reconstruction with partial MCUs

This isolated experiment enables fused reconstruction for even-sized baseline
8-bit 4:2:2 frames whose right or bottom edge ends inside a 16×8 MCU. Production
`src/` and `simd/`, existing archives, kernels, drivers and default aliases are
unchanged. Mode `fast 3` preserves the established stock-fast NV12 contract;
accurate and reduced-chroma modes retain their previous eligibility.

## Implementation

Interior MCUs retain direct paired Y and exact-fast paired Cb/Cr writes. An
edge MCU reconstructs a complete 16×8 Y tile and 16×4 interleaved UV tile into
192 bytes of local pixel storage. It copies only the visible columns and rows
into the destination. This handles 16×4 and 16×6 bottom tiles and 8×8 right
tiles, plus other even dimensions and right-and-bottom corners. The geometry
is derived from the JPEG header and MCU position, not camera identity.

Even widths/heights ensure UV copies contain complete Cb/Cr pairs and average
complete pairs of visible rows. Existing IDCT clipping, rounding, averaging,
quantizer handling and dummy coefficient-block conventions remain unchanged.
Odd-sized NV12 remains outside this prototype's contract. No entropy state,
restart logic or coefficient layout is changed.

The first version placed edge scratch storage directly in `mjpeg_fusion_mcu`.
Its cohort is retained under `inline-*`, including binary copies in `/tmp`.
Although edge frames improved, full-MCU controls showed overhead. The one
revision moves scratch work into an out-of-line helper and uses a per-frame
partial-geometry flag before checking individual MCU bounds. Both versions
remain reproducible (`build.py --inline` selects the initial version).

## Validation

Both versions pass:

- All 2,148 existing camera frames, both compilers and all existing method/mode
  checks, with literal pixel comparisons and padded/unaligned output checks.
- 128 coefficient-domain JPEG fixtures spanning every even width 2–32 and
  height 2–16; combined edges, small images, restart intervals and independent
  Cb/Cr quantizers. Five additional progressive fixtures retain fallback.
- 51 previous restart/table/fill fixtures and six original fixtures.
- Forced source suspension on 132 inputs: the 128 baseline synthetic fixtures
  and one frame from each affected camera resolution. Full versus chunked
  decoding and control versus candidate outputs/padding match. Each compiler
  and variant sees 2,894 suspensions, including 1,425 odd-column resumptions.
- Separate untimed counters verify edge/interior selection counts for all four
  affected resolutions and an aligned control. Diagnostics never enter timed
  binaries. The ordinary aligned control selects zero edge MCUs.

The same native wrapper is shared by Clang and GCC hosts, as in preceding
experiments. Core LTO, no PGO, no explicit CPU tuning; existing BMI2 entropy and
inline AVX2 coefficient zeroing retained. `build-summary.json` records source,
object, binary and archive hashes. `fusion.patch` contains the wrapper change.

## Reproduce

Requires the saved `next-round`, `multi-camera`, paired-transform and GCC
entropy artifacts; their preceding build recipes supply those prerequisites.
This is not a standalone clean-checkout build. Run commands sequentially:

```sh
python3 test/webcam/nv12/partial-mcu/build.py
python3 test/webcam/nv12/partial-mcu/check.py
python3 test/webcam/nv12/partial-mcu/state-check.py
python3 test/webcam/nv12/partial-mcu/run.py
```

Benchmarking compares against both stock-fast NV12 and the previous optimized
fallback, using the same twelve highest-requested-rate-mode captures per size.
The four affected Logitech sizes and aligned VGA/1080p controls use three
control/candidate/control brackets, sixty passes, reversed case order in the
middle round. CPU 0 on Ryzen 9 3900X; inputs preloaded, allocation/hashing
outside timing. No compilation or validation overlaps timing. Every bracket
must match output hashes. Raw rounds, including outliers, are retained.

## Revised helper results and selection

Milliseconds per frame; positive reductions mean less decode time. Each
comparison has its own adjacent controls and candidate samples; do not mix
their absolute candidate times.

### Against the previous optimized fallback

| Resolution | Clang control → edge ms | Less time | GCC control → edge ms | Less time |
|---|---:|---:|---:|---:|
| 320x180 | 0.1456 → 0.1247 | +14.35% | 0.1493 → 0.1257 | +15.80% |
| 424x240 | 0.3203 → 0.2818 | +12.02% | 0.3275 → 0.2875 | +12.23% |
| 480x270 | 0.3805 → 0.3338 | +12.28% | 0.3908 → 0.3351 | +14.24% |
| 960x540 | 1.2756 → 1.0852 | +14.93% | 1.3000 → 1.0888 | +16.24% |
| 640x480 | 0.6693 → 0.6730 | -0.55% | 0.6749 → 0.6811 | -0.92% |
| 1920x1080 | 3.5233 → 3.5538 | -0.87% | 3.5408 → 3.5567 | -0.45% |

### Against stock fast NV12

| Resolution | Clang control → edge ms | Less time | GCC control → edge ms | Less time |
|---|---:|---:|---:|---:|
| 320x180 | 0.1730 → 0.1254 | +27.49% | 0.1725 → 0.1255 | +27.23% |
| 424x240 | 0.4014 → 0.2813 | +29.92% | 0.3996 → 0.2850 | +28.69% |
| 480x270 | 0.4684 → 0.3316 | +29.20% | 0.4722 → 0.3385 | +28.32% |
| 960x540 | 1.5684 → 1.1007 | +29.82% | 1.5573 → 1.0907 | +29.96% |
| 640x480 | 0.9596 → 0.6700 | +30.18% | 0.9638 → 0.6767 | +29.78% |
| 1920x1080 | 5.1107 → 3.6257 | +29.06% | 5.1123 → 3.5616 | +30.33% |

The four partial-geometry resolutions improve in every bracket under both
compilers. Retain separate candidates for these workloads. Aligned VGA and
1080p controls still have small mean costs, so retain the previous full-MCU
selections and existing defaults. This experimental wrapper has no automatic
dispatch to the previous wrapper for fully aligned frames; the candidate
selection is deliberately explicit. No general default replacement is claimed.

The initial inline version also improves all four edge sizes, but aligned
controls cost more. Both full cohorts are saved; no round was discarded.
The revised Clang stock 1080p cohort includes a 3.7973 ms candidate outlier
and keeps it in the mean. One CPU, limited scenes and unfixed host clocks
remain limitations. Do not infer a universal gain from these measurements.

No further implementation variants were attempted. Production code, previous
executable aliases and full-MCU selections remain unchanged; no threading,
PGO, new CPU tuning, commit or push.
