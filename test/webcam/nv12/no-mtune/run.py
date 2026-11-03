#!/usr/bin/env python3
from pathlib import Path
import json,subprocess,statistics,hashlib
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-no-mtune')
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
fixtures=sorted(Path('/tmp/mjpeg-lut-pipeline/fixtures').glob('*.jpg'));assert len(fixtures)==6
mutations=[Path('/tmp/mjpeg-quantizer-cache')/f'changed-q{i}.jpg' for i in (1,2)];assert all(p.exists() for p in mutations)
build=json.loads((here/'build-summary.json').read_text());audit=json.loads((here/'audit.json').read_text());assert build['pgo'] is False and audit['explicit_mtune'] is False
for cases in build['cases'].values():
 for case in cases.values():
  for filename,wanted in case['sha256'].items():assert hashlib.sha256(Path(filename).read_bytes()).hexdigest()==wanted,filename
def save(n,v):(here/(n+'.json')).write_text(json.dumps(v,indent=2)+'\n')
def run(compiler,name,*args):
 p=subprocess.run(['taskset','-c','0',str(work/compiler/name/'nv12'),*map(str,args)],check=True,capture_output=True,text=True);assert not p.stderr,p.stderr;return json.loads(p.stdout)
expected=json.loads((here.parent/'lto-only/validation.json').read_text());validation={}
for compiler in ('clang','gcc'):
 stock=run(compiler,'stock','validate',1,*frames);assert stock==expected['stock'],compiler
 validation[compiler]={'stock':stock,'current':{}}
 for label,inputs in [('capture',frames),*[(p.stem,[p]) for p in fixtures],('changing-tables',[frames[60],mutations[0],*fixtures,mutations[1],frames[60],*fixtures[::-1],frames[60]])]:
  r=run(compiler,'current','validate',*inputs);assert r==expected['current'][label],(compiler,label);validation[compiler]['current'][label]=r
 print(compiler,'120-capture/fixtures/table-change validation matches, both IDCT modes and padding.',flush=True)
save('validation',validation)
rows=[];brackets=[]
for trial in range(5):
 for compiler in (('clang','gcc') if trial%2==0 else ('gcc','clang')):
  group=[]
  for name in ('stock','current','stock'):
   r=run(compiler,name,*(['measure',6,*frames[30:]] if name=='stock' else ['fast',2,6,*frames[30:]]));r.update(trial=trial,compiler=compiler,variant=name);rows.append(r);group.append(r)
  assert group[0]['hash']==group[2]['hash']
  assert group[1]['hash']==json.loads((here.parent/'lto-only/results.json').read_text())['records'][1]['hash']
  a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
  brackets.append(dict(trial=trial,compiler=compiler,stock_ms=a,current_ms=b,latency_reduction_percent=100*(1-b/a),throughput_speedup=a/b))
  save('results',dict(records=rows,brackets=brackets));print(brackets[-1],flush=True)
summary={}
for compiler in ('clang','gcc'):
 r=[v for v in brackets if v['compiler']==compiler];a=statistics.mean(v['stock_ms'] for v in r);b=statistics.mean(v['current_ms'] for v in r)
 summary[compiler]=dict(stock_ms=a,current_ms=b,stock_fps=1000/a,current_fps=1000/b,latency_reduction_percent=100*(1-b/a),throughput_speedup=a/b,brackets=r)
save('summary',{'pgo':False,'explicit_mtune':False,'cases':summary,'method':'CPU 0, five stock/current/stock brackets per compiler, alternating compiler order each round; 90 preloaded held-out 1920x1080 4:2:2 JPEGs, six measured passes after warmup. O3, no PGO or explicit mtune/march/mcpu, Clang ThinLTO or GCC LTO, same BMI2-on-entropy in stock/current, shared unchanged GCC native drivers/wrapper. Both fast Y; documented reduced-UV approximation retained. CPU JPEG-to-NV12 only.'})
print(json.dumps(summary,indent=2))
