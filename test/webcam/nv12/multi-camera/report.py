#!/usr/bin/env python3
from pathlib import Path
import sys,collections
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
inv=json.loads((here/'inventory.json').read_text());summary=json.loads((here/'summary.json').read_text());validation=json.loads((here/'validation.json').read_text());diag=json.loads((here/'diagnostics.json').read_text());assert len(validation)==29 and all(r['status']=='passed' for r in validation)
assert all(r['change_percent']<0 for r in summary if 'stock-vs' in r['comparison'])
short=lambda s:'Logitech C930e' if 'Logitech' in s else 'LifeCam Studio'
ct='| Camera | Resolutions | Modes | Frames |\n|---|---:|---:|---:|\n'
for c in inv:ct+=f"| {short(c['camera'])} | {len(c['groups'])} | {c['mode_count']} | {c['frame_count']} |\n"
table='| Camera | Size | Clang stock → exact | Less time | GCC stock → deferred exact | Less time |\n|---|---|---:|---:|---:|---:|\n'
for c in inv:
 for size in ('640x480','1280x720','1920x1080'):
  a=next(r for r in summary if r['batch']==c['batch'] and r['size']==size and r['comparison']=='clang-stock-vs-exact');b=next(r for r in summary if r['batch']==c['batch'] and r['size']==size and r['comparison']=='gcc-stock-vs-deferred')
  table+=f"| {short(c['camera'])} | {size} | {a['control_ms']:.3f} → {a['candidate_ms']:.3f} ms | {-a['change_percent']:.2f}% | {b['control_ms']:.3f} → {b['candidate_ms']:.3f} ms | {-b['change_percent']:.2f}% |\n"
follow='| Camera | Size | GCC deferred-field time change |\n|---|---|---:|\n'
for r in summary:
 if r['comparison']=='gcc-exact-vs-deferred':follow+=f"| {short(r['camera'])} | {r['size']} | {r['change_percent']:+.2f}% |\n"
inputs=[];camera_facts=[]
for c in inv:
 restarts=collections.Counter();rate_mismatches=0;gaps=0
 for p in sorted((ROOT/'test/webcam/mjpeg-modes/captures'/c['batch']).glob('*/manifest.json')):
  m=json.loads(p.read_text());inputs.append({'manifest':str(p),'sha256':sha(p),'stream_sha256':m['raw_stream_sha256'],'frames':m['frame_count']})
  for f in m['frames']:
   h=f['header'];restarts[h['restart_interval']]+=1
   if 'Microsoft' in c['camera']:assert h['restart_interval']==(h['width']+15)//16
   else:assert h['restart_interval']==0
  gaps+=m['sequence_gaps']
  rate_mismatches+=bool(m['observed_fps'] and abs(m['observed_fps']/float(m['requested']['fps'])-1)>.1)
 camera_facts.append({'camera':c['camera'],'restart_intervals':dict(restarts),'sequence_gaps':gaps,'modes_with_observed_rate_over_10_percent_from_request':rate_mismatches})
save(here/'capture-inputs.json',inputs);save(here/'capture-findings.json',camera_facts)
text='''# Two-camera MJPEG mode validation and NV12 performance

All **2,148 new camera frames** pass stock-fast-exact NV12 checks, including
the GCC deferred-field experiment. Performance is workload-dependent: the
Logitech gains about 30%; the LifeCam gains about 8–15%. The LifeCam's restart
markers force the existing slow entropy path, explaining why the fused entropy
loop and its GCC source rewrite do not contribute there.

## Actual captured modes

'''+ct+'''
Both cameras emit baseline 8-bit 4:2:2 JPEG, but have different DHT segment
hash signatures. Logitech has 17 resolutions and seven advertised rates
(5, 7.5, 10, 15, 20, 24, 30 fps). LifeCam has 12 resolutions and five rates
(7.5, 10, 15, 20, 30 fps). Twelve original frames were captured per mode.
`inventory.json` records every size/rate and local frame path.

Hashes, byte lengths and per-buffer offsets reconstruct every raw stream
exactly. JPEG dimensions, sampling and headers agree with manifests. The
179 mode captures all succeeded. The Logitech has one driver-sequence gap;
LifeCam has none. Actual arrival rates differ from requested nominal rates by
more than 10% in 31 Logitech and 23 LifeCam modes. These short capture windows
are not camera-rate certification; requested, negotiated and observed rates
remain separate. Their cause was not isolated.

The Logitech's original format/rate restoration verified. LifeCam returned to
640x480 YUYV, but the driver selected 7.5 fps when asked to restore its reported
original 5 fps. This was already flagged as `original_restored: false`, not
hidden or treated as full success. Camera device nodes remain unavailable in
the agent sandbox; the user ran capture on the host. This validation made no
camera-setting changes.

## Geometry-aware validation

The earlier runners hardcoded 1920x1080. `build.py` regenerates their application
drivers to obtain width/height from the first JPEG in each same-size group;
it sizes native plane buffers accordingly. Codec archives, entropy sources,
Y/UV kernels, packing arithmetic and production src/simd remain unchanged.

All 29 camera/resolution groups pass:

- Stock public TurboJPEG fast decoding versus raw strips, scalar versus AVX2
  packing, and padded/unaligned destinations with unchanged padding.
- Whole NV12 hashes against stock fast for Clang and GCC optimized mode 3;
  full literal arrays are also compared inside the candidate driver against
  ordinary raw decoding. No accurate-IDCT equivalence is claimed for IFAST.
- Accurate and fast methods with modes 1/2/3; the GCC deferred-field source
  returns exactly the prior GCC reports for every group.
- 1,812 full-MCU frames eligible for fused reconstruction, plus 336 Logitech
  frames using generic fallback due to width/height alignment. These include
  320x180, 424x240, 480x270 and 960x540, with partial right/bottom MCU coverage.
- Alternating both cameras at VGA, 720p and 1080p, exercising cached Huffman and
  quantizer refresh in the same persistent decoders (24 frames per stream).

`validation.json` and `mixed-validation.json` retain reports. The reduced-UV
mode's previous approximation remains distinct; the separate zero-group UV
wrapper was not newly benchmarked in this batch. No RGB utilities or broad
CTest suite were used.

## Fresh exact-output timings

'''+table+'''
Every stock-versus-optimized bracket improves. These are new inputs and a
newly linked geometry-aware application; do not substitute these absolute
numbers into the previous single-scene cohort or combine their controls.
Clang uses its original entropy source; GCC optimized uses the deferred-field
source. Both retain paired fast Y and stock-fast-exact Cb/Cr reconstruction.

Each cell averages three control/candidate/control brackets, 30 timed passes
over the 12 files of the highest-requested-rate mode, preloaded with warmup.
Whole frame setup/decoding/packing is timed; file loading, allocation and
hashing are outside. Case order reverses in the middle round. CPU 0 on Ryzen
9 3900X; O3, Clang ThinLTO/GCC LTO, no PGO, no explicit CPU tuning, matched
BMI2 entropy and unchanged shared native support. Compiler defaults, including
GCC's protection settings, remain as documented in compiler-gap. Builds,
validation, diagnostics and measurement ran sequentially, without competition
from another agent workload. Raw rounds include all variability.

The 1080p identical-GCC-binary noise means are -0.01% Logitech and -0.18%
LifeCam, with individual brackets roughly within +/-0.54%. Short input sets,
scene/exposure differences and unfixed machine clocks limit generalization.
This remains one CPU, not a cross-architecture default recommendation.

## What happened to the GCC field-access improvement?

Negative means less time against the previous optimized GCC exact path:

'''+follow+'''
The rewrite helps the new Logitech captures too (all nine brackets improve).
LifeCam changes are small/mixed; no reliable improvement is established there.
It must not be advertised as a universal 5–6% win. The source expression itself
uses runtime tables and remains input-independent; performance depends on
whether that loop is reached.

## Restart markers explain the path difference

All Logitech frames have DRI=0. Every LifeCam frame has DRI equal to the MCU
row width: at 1080p, 120 MCUs between restart markers. The unchanged controller
in `jdhuff.c` sets `usefast=0` whenever `restart_interval` is nonzero, even away
from an individual marker boundary. Thus the entire LifeCam entropy scan uses
the slow decoder; paired reconstruction still applies.

An untimed existing diagnostic build, on the twelve 1080p high-rate captures:

| Camera | Fast MCU calls | Slow MCU calls | Fused lookup hits |\n|---|---:|---:|---:|\n| Logitech | 193,534 | 866 | 4,180,654 |\n| LifeCam | 0 | 194,400 | 0 |\n
The diagnostic deliberately skips reconstruction and is not valid NV12 timing.
It is ordinary counter instrumentation, not a training profile or PGO.
`diagnostics.json` retains counts, coefficient density and input byte sizes.
The empty LifeCam fast-path counts are meaningful, not missing measurements.

This supplies a concrete next hypothesis: a **restart-aware fast entropy
path**, preserving marker boundaries, bit alignment, DC resets, rollback and
suspension. Restart-separated row parallelism is another possible later
experiment for this camera. Neither was implemented here; simply removing
the guard is not a validated optimization. Different table and image content
can also affect timings, so we do not assign the whole cross-camera gap to
one feature based on the diagnostic alone.

## Reproduce and artifacts

```
python3 test/webcam/nv12/multi-camera/inventory.py
python3 test/webcam/nv12/multi-camera/build.py
python3 test/webcam/nv12/multi-camera/check.py
python3 test/webcam/nv12/multi-camera/mixed-check.py
python3 test/webcam/nv12/multi-camera/audit.py
python3 test/webcam/nv12/multi-camera/run.py
python3 test/webcam/nv12/multi-camera/diagnostics.py
python3 test/webcam/nv12/multi-camera/report.py
```

Requires the two ignored capture batches, saved no-mtune/paired-fast-chroma
artifacts and the GCC deferred source candidate. The diagnostic probe comes
from next-round. Missing captures are prerequisites, not silently substituted.
`capture-inputs.json` hashes every raw input manifest; each manifest records
all JPEG hashes. `build-summary.json`, `audit.json` and `manifest.json` record
binary/archive provenance. Generated drivers and executables remain under
/tmp/mjpeg-multi-camera and /tmp/mjpeg-next-round/bin. Existing selections are
unchanged; no production sources, commits or pushes changed.
'''
(here/'README.md').write_text(text)
files=[p for p in here.iterdir() if p.is_file() and p.name!='manifest.json']
files += list(Path('/tmp/mjpeg-multi-camera').glob('*'))
files += list((WORK/'bin').glob('*camera*'))
for r in json.loads((here/'build-summary.json').read_text())['records'].values():files += [Path(p) for p in r['archives']]
save(here/'manifest.json',{'sha256':{str(p):sha(p) for p in sorted(set(files)) if p.is_file()}})
print('Multi-camera report, capture findings/input hashes and artifact manifest saved.')
