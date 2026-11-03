#!/usr/bin/env python3
from pathlib import Path
import json,re,hashlib
here=Path(__file__).resolve().parent;W=Path('/tmp/mjpeg-compiler-gap')
s=json.loads((here/'summary.json').read_text());h=json.loads((here/'hardening-summary.json').read_text());asm=json.loads((here/'assembly.json').read_text());perf=json.loads((here/'perf.json').read_text())
# Compact the wide perf report formatting; full disassembly stays under /tmp.
for row in perf:row['report']='\n'.join(re.sub(r' {2,}','  ',l).rstrip() for l in row.get('report','').splitlines())+'\n'
(here/'perf.json').write_text(json.dumps(perf,indent=2)+'\n')
table='| Rest of codec built by | Clang entropy | GCC entropy | GCC extra time |\n|---|---:|---:|---:|\n'
for cc,r in s.items():table+=f"| {cc} | {r['clang_entropy_ms']:.4f} ms | {r['gcc_entropy_ms']:.4f} ms | {r['gcc_change_percent']:.2f}% |\n"
r=h['matched-hardening']
measures={}
for e in ['cycles:u','instructions:u','branches:u','branch-misses:u']:
 counts=[int(next(l.split(',')[0] for l in p['stderr'].splitlines() if ',,'+e+',' in l)) for p in perf]
 measures[e]={'clang':counts[0],'gcc':counts[1],'gcc_extra_percent':100*(counts[1]/counts[0]-1)}
profile={}
for cc in ['clang','gcc']:
 entries=[]
 for l in (W/(cc+'-perf-annotate.txt')).read_text().splitlines():
  m=re.match(r'\s*([0-9.]+)\s*:\s*([a-f0-9]+):\s*(.*)',l)
  if m:entries.append({'local_sample_percent':float(m[1]),'address':m[2],'instruction':m[3]})
 profile[cc]=sorted(entries,key=lambda x:x['local_sample_percent'],reverse=True)[:20]
(here/'profile-summary.json').write_text(json.dumps({'whole_process_counter_differences':measures,'top_sampled_entropy_instructions':profile,'caution':'Counters include startup/loading/warmup/hashing; samples can skid and do not measure exact instruction latency.'},indent=2)+'\n')
text='''# Why Clang beats GCC on the exact NV12 path

The main difference follows the scalar entropy translation unit, rather than
the native reconstruction kernels or the compiler used for the rest of the
codec. Clang 18.1.3 and Ubuntu GCC 13.3.0 compile the same entropy source quite
differently. This is evidence for this source/workload/Zen 2 CPU, not a general
compiler ranking. No production sources or existing selections changed.

## Controlled entropy-object crossover

'''+table+'''
Five Clang-entropy/GCC-entropy/Clang-entropy brackets in each host, six passes
over 90 preloaded capture frames, CPU 0 on Ryzen 9 3900X. Host order rotates;
all ten brackets favor Clang entropy. Full arrays/validation reports match
for all 120 captures, all IDCT/mode combinations, six boundary fixtures,
independent chroma quantizers, mixed inputs and padded output.

Each comparison replaces only `jdhuff.c.o` in both otherwise unchanged codec
archives. Identical driver, wrapper, Y NASM and exact-fast Cb/Cr NASM objects
are linked throughout. The entropy objects are **native, non-LTO** on both
sides, because GCC LTO and LLVM bitcode cannot be crossed directly. The rest
of each host retains its original LTO. This isolates compiler output for one
translation unit, not the exact effect of LTO or a literal decomposition of
our earlier headline timing gap. No PGO, explicit CPU tuning or source
algorithm changes. BMI2 remains enabled for entropy only. Generated config
headers are byte-identical between the baseline compilers.

Earlier isolated entropy/controller probes were 2.501 ms Clang and 2.711 ms
GCC, while final exact NV12 confirmation was 3.162 versus 3.357 ms. Those are
separate cohorts and cannot be subtracted as exact accounting; they support
the same localization. The native reconstruction support is identical.

## Compiler defaults checked explicitly

Ubuntu GCC's driver adds stack-protector-strong and full control-flow protection
by default. The Clang baseline entropy body has neither a canary nor endbr64;
GCC has both. Thus matching requested O3/LTO/ISA flags did not match every
compiler-default protection setting. `audit.json` retains driver expansion.

We repeated the entropy comparison in the same Clang host with **both** objects
explicitly built with `-fstack-protector-strong -fcf-protection=full`:

'''+f"Clang entropy **{r['control_ms']:.4f} ms**, GCC entropy **{r['candidate_ms']:.4f} ms**; GCC takes **{r['change_percent']:.2f}%** longer. All three six-pass brackets agree.\n"+'''
Both resulting entropy bodies contain canary checks and endbr64. The explicitly
protected GCC object is byte-identical to its default object. Clang with
protection was slightly faster in the separate default-versus-protected
cohort, with a varying effect, so we do not infer a fixed protection tax.
Crucially, matching protections does not erase the compiler gap. No protections
were disabled and this does not change previous preferred binaries.

## Assembly and sampled behavior

The active original entropy function, followed through `jinit_huff_decoder`
rather than a misleading duplicate private symbol, is:

| Static property | Clang | GCC |
|---|---:|---:|
| Function bytes | 5,347 | 6,913 |
| Instruction sites | 1,342 | 1,617 |
| Stack-memory operand sites | 73 | 147 |

These count whole functions, including cold paths, and are not dynamic spill
counts or proof that code size alone causes the difference. GCC's function
also has a larger stack reservation (200 versus 152 bytes).

There is a concrete difference in the hot fused-AC lookup sequence. GCC loads
both coefficient values, consumed bits, first position step and combined span
before testing whether the entry is usable. Clang first loads/tests consumed
bits, then the span/boundary guard, and loads coefficient values/step only on
success. On failed fused lookups, Clang avoids several load instructions.
Both access the same small table entries: this is not evidence of extra cache
misses or memory-bandwidth pressure. Scheduling and register allocation also
differ; the crossover does not assign an exact fraction of the gap to each.

Longer whole-process `perf stat` runs on the original fully LTO binaries show
GCC retiring **4.50% more instructions**, **3.82% more branches** and **6.85%
more cycles**. Branch misses increase only 1.58% in count; rates are 4.99%
Clang versus 4.88% GCC, so a worse overall misprediction rate does not explain
the gap. These counters include loading, warmup and output hashing, not just
the timed decode region. Both runs have the same output hash and 24 timed
passes over 90 frames; their measured decode means are 3.171 and 3.399 ms.

Separate cycles sampling puts 70.50% of Clang and 73.22% of GCC process samples
in the active entropy function. Hot samples concentrate in the fused lookup,
coefficient position/dezigzag stores and fallback decisions. Sample skid and
out-of-order execution mean a sampled mov/lea is not a measurement of that
instruction's latency. `profile-summary.json` retains top sampled sites;
raw perf data, full annotation and assembly remain under /tmp.

## Conclusion and limits

The experiments establish a translation-unit code-generation advantage for
Clang on the current entropy loop, persisting after matched protection flags.
The larger GCC implementation, extra hot-loop work and register/stack behavior
are identifiable contributors/hypotheses; their separate cycle costs have not
been isolated. This does not establish a single compiler bug, identify one
optimization pass, or prove the same ordering for other CPUs/JPEG scenes.
No speculative source rewrite or new mixed-compiler default was selected.

```
python3 test/webcam/nv12/compiler-gap/build.py
python3 test/webcam/nv12/compiler-gap/inspect.py
python3 test/webcam/nv12/compiler-gap/run.py
python3 test/webcam/nv12/compiler-gap/hardening.py build
python3 test/webcam/nv12/compiler-gap/hardening.py run
python3 test/webcam/nv12/compiler-gap/perf.py
python3 test/webcam/nv12/compiler-gap/audit.py
python3 test/webcam/nv12/compiler-gap/report.py
```

Prerequisites are the retained no-mtune and paired-fast-chroma builds, with
source recovery described in next-round. Run phases sequentially; do not
compile/profile concurrently with timing. No commit or push was performed.
'''
(here/'README.md').write_text(text)
files=[p for p in here.iterdir() if p.is_file() and p.name!='manifest.json']
files += [p for p in W.rglob('*') if p.is_file() and p.suffix in ('.a','.o','.asm')]
files += list(Path('/tmp/mjpeg-next-round/bin').glob('*gap*'))
(here/'manifest.json').write_text(json.dumps({'sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}},indent=2)+'\n')
print('Report, counter/sample summary and manifest saved.')
