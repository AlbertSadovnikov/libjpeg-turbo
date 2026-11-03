#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,subprocess
here=Path(__file__).resolve().parent;W=Path('/tmp/mjpeg-gcc-deferred-loads');initial=json.loads((here/'summary.json').read_text());confirm=json.loads((here/'confirm-summary.json').read_text());build=json.loads((here/'build-summary.json').read_text())['records']
assert build['gcc-control']['sha256']==build['gcc-no-hoist']['sha256']
table='| Compiler | Control | Deferred fields | Time change |\n|---|---:|---:|---:|\n'
for cc in ['gcc','clang']:
 r=confirm[cc+'-deferred'];table+=f"| {cc} | {r['control_ms']:.4f} ms | {r['candidate_ms']:.4f} ms | {r['change_percent']:+.2f}% |\n"
perf=json.loads((here/'perf.json').read_text());counts={}
for event in ['cycles:u','instructions:u','branches:u','branch-misses:u']:
 values=[int(next(l.split(',')[0] for l in r['stderr'].splitlines() if ',,'+event+',' in l)) for r in perf]
 counts[event]={'control':values[0],'deferred':values[1],'change_percent':100*(values[1]/values[0]-1)}
(here/'counter-summary.json').write_text(json.dumps(counts,indent=2)+'\n')
text='''# GCC lookup-field access: flag versus source expression

Retain the deferred-field source experiment for GCC. It reduces exact NV12
decode time by 5.17% in a separate confirmation cohort, preserving all tested
coefficients and output bytes. Keep the original Clang implementation: this
rewrite provides no Clang benefit. Production sources and previous preferred
selections remain unchanged.

## Results

`-fno-hoist-adjacent-loads` applied only to the GCC entropy translation unit
produces a **byte-identical complete executable** to the recompiled control.
The flag is present in the archived GCC LTO options, but changes no emitted
code here. It is not a useful knob for this implementation. No separate timing
cohort for this duplicate binary is needed; one identical-binary noise cohort
is already included.

Separate three-bracket confirmation, six passes over 90 preloaded frames:

'''+table+'''
Every GCC confirmation bracket improves (4.54–5.70% less time). The first
five-bracket cohort improved in every GCC round too: 3.4084 → 3.2404 ms,
4.93% less time. Its identical-binary control mean changed -0.06%, with
individual changes from -1.39% to +1.32%. Clang's initial mean changed +0.55%
and confirmation +0.63%, with mixed rounds; no Clang gain is established.
The unchanged Clang controls averaged 3.1812 ms in confirmation, versus
3.2180 ms for the new GCC candidate: the original gap is substantially reduced.
These are interleaved cohort means, not a separate direct compiler bracket.
There is no fresh stock-versus-new-candidate headline measurement in this batch.

O3, GCC LTO / Clang ThinLTO, no PGO, no explicit mtune/march/mcpu. Entropy
retains BMI2; GCC retains its default stack and control-flow protection.
Shared native driver/Y/UV objects are unchanged. CPU 0 on Ryzen 9 3900X;
compiler/variant order rotates, controls bracket each candidate. Loading,
allocation, output hashing and diagnostics remain outside decode timing.
Benchmarks, fixture timings and counter collection run sequentially with no
concurrent compilation/validation. Raw rounds and regressions are retained.

## What changed

The old C expression copies the complete eight-byte lookup entry before
checking its validity. Clang can delay unused field loads; GCC loads several
fields immediately. The rewrite uses a pointer, caches consumed-bit count,
and accesses coefficient values/position fields inside the accepted branch:

```c
const multi_entry *e = &fused[prefix];
const int entry_bits = e->bits;
const int next_k = k + e->span;
if (entry_bits && next_k <= DCTSIZE2) {
    /* Access e->step1, e->value1 and e->value2 here. */
}
```

The actual reviewable source change is `deferred.patch`; no branches, bounds
rules, arithmetic or fallback algorithms were added or removed. There are no
volatile reads, compiler barriers or hardcoded Huffman definitions. It uses
each input's runtime tables, so this is not camera/table specialization.
Because the old struct copy already appears before the guard in the source,
disabling an adjacent-load-hoisting pass need not change its placement.

The resulting GCC assembly really does delay coefficient/step loads until the
guard succeeds. Static stack-memory operand sites decrease from 147 to 122,
while whole-function instruction sites increase from 1,617 to 1,647. The
recompiled control normalizes identically to the previous GCC entropy body.
`audit.json` retains code hashes and checks default canary/endbr64 protection.
Static site counts include cold paths; they are not dynamic spill counts.

Whole-process counters over 24 timed passes show fewer cycles despite slightly
more retired instructions. The rewrite also changes scheduling, allocation
and layout; this experiment does not isolate a cycle saving for each omitted
load. Counter totals include input loading, warmup and hashing, so they are
supporting context rather than decode-only attribution. `perf.json` and
`counter-summary.json` retain all counts and measured output hashes.

## Correctness and scene limits

All four builds match complete validation reports for 120 real capture frames,
accurate/fast IDCT, modes 1/2/3 and padded output. Mixed-stream checks include
six fixtures (dense, zero-AC, optimized tables, progressive, restart-per-MCU
and high-frequency tail), independent Cb/Cr quantizer selections and changed
Y quantizers. All 130 literal serialized coefficient/table streams match for
every variant, including the source rewrite under both compilers.

Synthetic scene timings use three control/candidate/control brackets each,
50 passes per invocation. GCC dense improves about 10.7% in the first two
brackets but regresses 16.57% in the third; that candidate invocation is slow
throughout, including its median, while adjacent controls remain stable.
Retain this observation: its cause was not established. A separate three-
bracket, 100-pass repeat improves 9.00–10.32% in every round. Do not discard
the original regression or claim uniformly better dense-scene behavior.
GCC zero-AC changes -0.86% to -1.38%. Clang dense regresses 1.10–4.37%, and
zero-AC is roughly flat. These results support retaining a separate GCC
candidate, not applying the patch globally to both compiler builds.

One real scene and one CPU remain the broad-coverage limitation. This
source change does not depend on a particular feed's tables, but its speedup
is not established across arbitrary cameras, CPUs or GCC versions.

## Candidate and reproduction

`candidate.json` records `/tmp/mjpeg-gcc-deferred-loads/nv12`, mode 3 and its
hash. This is a separate GCC candidate; the established Clang exact-fast and
reduced-UV aliases are unchanged. No production src/simd edits, commit or push.

```
python3 test/webcam/nv12/gcc-deferred-loads/build.py
python3 test/webcam/nv12/gcc-deferred-loads/audit.py
python3 test/webcam/nv12/gcc-deferred-loads/check.py
python3 test/webcam/nv12/gcc-deferred-loads/run.py
python3 test/webcam/nv12/gcc-deferred-loads/run.py --confirm
python3 test/webcam/nv12/gcc-deferred-loads/fixtures-perf.py
python3 test/webcam/nv12/gcc-deferred-loads/confirm-dense.py
python3 test/webcam/nv12/gcc-deferred-loads/perf.py
python3 test/webcam/nv12/gcc-deferred-loads/choose-candidate.py
python3 test/webcam/nv12/gcc-deferred-loads/report.py
taskset -c 0 /tmp/mjpeg-gcc-deferred-loads/nv12 fast 3 6 JPEG...
```

Requires retained no-mtune/paired-fast-chroma builds and coefficient reference
helper from next-round; their reconstruction scripts are saved in those
folders. Generated source, archives, objects and disassembly stay under /tmp.
`manifest.json` hashes durable scripts/results and generated binary artifacts.
'''
(here/'README.md').write_text(text)
subprocess.run(['git','diff','--exit-code','--','src','simd'],check=True)
files=[p for p in here.iterdir() if p.is_file() and p.name!='manifest.json']
files += [p for p in W.rglob('*') if p.is_file() and (p.suffix in ('.a','.o','.asm','.c') or p.name=='nv12')]
files += list(Path('/tmp/mjpeg-next-round/bin').glob('*loads*'))
(here/'manifest.json').write_text(json.dumps({'production_src_simd_diff_empty':True,'sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}},indent=2)+'\n')
print('Report and artifact manifest saved.')
