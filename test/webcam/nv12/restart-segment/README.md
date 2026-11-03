# Single-thread restart-segment controller

Experimental JPEG → NV12 controller for eligible baseline 8-bit 4:2:2 restart
scans. No production sources or existing executable aliases are changed.
Final timing and selection are recorded below after execution.

The controller clips each group to the header's restart interval and the
remaining MCU row. It keeps bit/DC state local across completed fast MCUs,
uses direct entropy routines instead of an indirect per-MCU callback, and
updates restart accounting per group. It reconstructs each MCU immediately
using the existing paired kernels and one coefficient buffer. There is no
threading, restart-marker prescan, or assumption that intervals equal rows.
The final MCU of an interval uses the safe slow path. Marker-lookahead aborts
clear partial coefficients and replay from completed-MCU state. Before a slow
read, local state is flushed; after suspension the source-manager state is
preserved and only completed MCUs advance. DRI 1 and unsupported configurations
retain the existing decoder. Selection is structural, never a camera-name test.

`adapter.c` retains the original application driver and wraps its fusion
registration call. The mode-3 controller is installed only after successful
fusion registration. `MJPEG_SEGMENT=0` disables it; `1` enables it (default).
Configuration happens outside the timed decode loop.

## Reproduce

This experiment builds on the saved `restart-tu` and earlier native-kernel
artifacts. It is not a standalone clean-checkout codec build. Reconstruct those
prerequisites using their saved recipes first. From the repository root:

```sh
python3 test/webcam/nv12/restart-segment/build.py --wrapped
python3 test/webcam/nv12/restart-segment/audit.py
python3 test/webcam/nv12/restart-segment/check.py
python3 test/webcam/nv12/restart-segment/run.py
python3 test/webcam/nv12/restart-segment/run.py --confirm
python3 test/webcam/nv12/restart-segment/scene-run.py
```

Run each command sequentially. No compilation or validation overlaps timing.
Clang/GCC use the existing unprofiled LTO core archives, matched BMI2 entropy,
shared native transform/support objects, and no explicit mtune/march/mcpu.
The isolated restart and segment units use O3, `-fno-lto`, `-mbmi2`; this keeps
new code outside core LTO. Existing inline AVX2 MCU zeroing is retained.
`build-summary.json` records exact object/archive/binary hashes and flags.

## Validation and attribution

- All 2,148 frames from both camera inventories: modes, exact-fast/accurate
  comparisons, padding and alternating-camera checks.
- 51 restart/table/fill fixtures, including intervals that cross row boundaries.
- 2,325 actual raw-controller coefficient streams, compared literally against
  the control and across compilers; 767 inputs select the segment controller.
- 127,934 forced suspensions per compiler per variant across 23 inputs, with
  full-output hash equality, including 63,265 odd-column resumptions.
- The wrapped revision reran NV12/fixture/suspension validation. Its controller
  objects are byte-identical to the initial fully traced version; coefficient
  evidence was retained after checking those hashes.
- `audit.json` verifies original entropy and coefficient-controller instructions
  against the frozen executable, resolving unnamed CET PLT entries before
  comparison. It also verifies the registration wrapper is bound. No original
  core archive changes are made by this experiment.

Timing loads inputs before measurement, pins CPU 0 on the same Ryzen 9 3900X,
and saves every bracket. Primary runs use three control/candidate/control
brackets, twenty passes over twelve frames; confirmation uses sixty passes
at 1080p. Same-executable toggles isolate controller selection; separate frozen
reference comparisons include packaging effects. LifeCam control/control
brackets measure local noise. Logitech has no restart markers and provides
fallback and packaging controls. Output hashes must match within each bracket.

The initial driver-hook implementation and its entire cohort are preserved
as `initial-*`. It showed a same-executable benefit but much smaller GCC gains
against the frozen executable. The one revision uses the original driver plus
a registration adapter. The revised frozen-reference runs also match the
presence/value of the MJPEG_SEGMENT environment entry; the initial reference
runs did not. These cohorts are reported separately, not pooled. Matching core
instructions does not guarantee identical whole-program layout or performance.

## Results and selection

Confirmation, 1080p; negative change means less decode time. The reference is
the previous isolated restart-aware candidate, **not stock decoding**.

| Camera | Compiler | Comparison | Control ms | Segment ms | Change |
|---|---|---|---:|---:|---:|
| Logitech | clang | same executable | 3.4110 | 3.5132 | +3.00% |
| Logitech | clang | frozen reference | 3.4496 | 3.4462 | -0.10% |
| Logitech | gcc | same executable | 3.5364 | 3.5427 | +0.18% |
| Logitech | gcc | frozen reference | 3.4937 | 3.5416 | +1.37% |
| LifeCam | clang | same executable | 4.0581 | 3.8846 | -4.27% |
| LifeCam | clang | frozen reference | 3.9933 | 3.8872 | -2.66% |
| LifeCam | gcc | same executable | 4.0850 | 3.9569 | -3.14% |
| LifeCam | gcc | frozen reference | 3.9299 | 3.9491 | +0.49% |

Retain the Clang binary as an explicit LifeCam/restart experiment. Its frozen-
reference improvement repeats in all primary and confirmation 1080p brackets.
Keep the previous GCC candidate: this new loop improves the same-executable
control but the whole executable does not beat the frozen reference. This
difference is a measured packaging/code-layout effect; its precise cause is
not cycle-isolated. Do not infer it from instruction counts alone.

The Logitech same-executable Clang confirmation includes a retained +8.67%
outlier, producing a +3.00% mean despite the controller never being selected
on these inputs. Its other two brackets are +0.04%/+0.27%, and the independent
frozen-reference mean is -0.10% (mixed bracket signs). Primary means were
-0.31%/-0.81%, respectively. This is evidence of runtime variability, not a
basis to delete a round or promise universal no-regression. GCC frozen-
reference Logitech is consistently about 1.37% slower in confirmation.

Short synthetic intervals, same-executable comparisons against the previous
restart decoder (three brackets, fifty passes):

| Scene | Clang change | GCC change |
|---|---:|---:|
| dense-rst2.jpg | -0.00% | +2.02% |
| ordinary-fill-rst3.jpg | -3.07% | -2.08% |
| ordinary-rst1.jpg | -0.26% | -0.19% |
| ordinary-rst2.jpg | -2.58% | -2.41% |
| zeroac-rst3.jpg | -3.22% | -8.23% |

These fixtures compare the new segment loop with the previous restart-aware
candidate, not with stock or the pre-restart decoder. They do not erase the
earlier sparse-restart regressions. GCC dense DRI-2 adds roughly 2%; Clang
dense DRI-2 is neutral. DRI-1 stays on fallback. No broader default is selected.

The approved implementation and one packaging revision are complete. Further
layout tuning, a second CPU and varied scenes are future work. No threading,
PGO, explicit CPU tuning, production change, commit or push was introduced.

## All-resolution follow-up

[Complete tables and protocol](ALL_RESOLUTIONS.md) cover all 17 Logitech and
12 LifeCam captured resolutions with both compilers. All 174 brackets pass
output-hash equality. This is a separate fixed-build cohort versus the previous
restart-aware candidate; it does not overwrite the earlier measurements.
