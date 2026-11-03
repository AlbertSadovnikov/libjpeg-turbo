#!/usr/bin/env python3
"""Current overall numbers: matched no-PGO codecs with ThinLTO on both sides."""
from pathlib import Path
import json,subprocess,statistics,hashlib
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-lto-only')
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
fixtures=sorted(Path('/tmp/mjpeg-lut-pipeline/fixtures').glob('*.jpg'));assert len(fixtures)==6
build=json.loads((here/'build-summary.json').read_text());assert build['pgo'] is False
for name in ('stock','current'):assert hashlib.sha256((work/name/'nv12').read_bytes()).hexdigest()==build['cases'][name]['binary_sha256']
assert json.loads((here/'no-pgo-audit.json').read_text())['pgo'] is False
def save(n,v):(here/(n+'.json')).write_text(json.dumps(v,indent=2)+'\n')
def run(name,*args):
 p=subprocess.run(['taskset','-c','0',str(work/name/'nv12'),*map(str,args)],check=True,capture_output=True,text=True);assert not p.stderr,p.stderr;return json.loads(p.stdout)
# Historical hashes are correctness oracles only; no historical PGO executable
# is run, linked, or timed in this comparison.
stock_validation=run('stock','validate',1,*frames)
assert stock_validation==json.loads((here.parent/'stock-fast/validation.json').read_text())
expected=json.loads((here.parent/'entropy-span/validation.json').read_text());validation={'stock':stock_validation,'current':{}}
mutations=[Path('/tmp/mjpeg-quantizer-cache')/f'changed-q{i}.jpg' for i in (1,2)];assert all(p.exists() for p in mutations)
for label,inputs in [('capture',frames),*[(p.stem,[p]) for p in fixtures],('changing-tables',[frames[60],mutations[0],*fixtures,mutations[1],frames[60],*fixtures[::-1],frames[60]])]:
 r=run('current','validate',*inputs);assert r==expected[label],label;validation['current'][label]=r
save('validation',validation);print('Fresh no-PGO stock/current outputs match all existing capture/fixture correctness oracles.',flush=True)
rows=[];brackets=[]
for trial in range(5):
 group=[]
 for name in ('stock','current','stock'):
  r=run(name,*(['measure',6,*frames[30:]] if name=='stock' else ['fast',2,6,*frames[30:]]));r.update(trial=trial,variant=name);rows.append(r);group.append(r)
 assert group[0]['hash']==group[2]['hash']
 if trial:assert group[1]['hash']==next(r['hash'] for r in rows if r['variant']=='current')
 a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
 brackets.append(dict(trial=trial,stock_ms=a,current_ms=b,latency_reduction_percent=100*(1-b/a),throughput_speedup=a/b))
 save('results',dict(records=rows,brackets=brackets));print(brackets[-1],flush=True)
a=statistics.mean(r['stock_ms'] for r in brackets);b=statistics.mean(r['current_ms'] for r in brackets)
summary=dict(pgo=False,lto='ThinLTO in both complete codecs',stock_ms=a,current_ms=b,saved_ms=a-b,stock_fps=1000/a,current_fps=1000/b,latency_reduction_percent=100*(1-b/a),throughput_speedup=a/b,throughput_increase_percent=100*(a/b-1),brackets=brackets,stock_binary_sha256=build['cases']['stock']['binary_sha256'],current_binary_sha256=build['cases']['current']['binary_sha256'],method='Five stock/current/stock brackets, CPU 0, 90 preloaded held-out 1920x1080 4:2:2 capture frames, six measured passes after warmup. Both complete codecs freshly built with identical Clang O3/mtune=znver2/ThinLTO and BMI2-on-entropy settings, no PGO anywhere. Shared native GCC C++ drivers/wrapper retain UV output contract. CPU decode-to-NV12 only; load/allocation/hash/GPU upload/encode excluded. Fast Y in both, documented reduced-UV output difference remains.')
save('summary',summary);print(json.dumps(summary,indent=2))
