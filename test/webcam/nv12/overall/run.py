#!/usr/bin/env python3
"""Overall stock-fast versus selected span candidate, complete JPEG to NV12."""
from pathlib import Path
import json,subprocess,statistics,hashlib
here=Path(__file__).resolve().parent;root=here.parents[3]
stock=Path('/tmp/mjpeg-stock-nv12/stock-fast-nv12');candidate=Path('/tmp/mjpeg-entropy-span/nv12')
stock_build=json.loads((here.parent/'stock-fast/build-summary.json').read_text());assert hashlib.sha256(stock.read_bytes()).hexdigest()==stock_build['binary_sha256']
selection=json.loads((here.parent/'entropy-span/preferred-candidate.json').read_text())
assert hashlib.sha256(candidate.read_bytes()).hexdigest()==selection['sha256'][str(candidate.resolve())]
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
rows=[];brackets=[]
for trial in range(3):
 group=[]
 for name in ('stock','current','stock'):
  cmd=[stock,'measure',6,*frames[30:]] if name=='stock' else [candidate,'fast',2,6,*frames[30:]]
  p=subprocess.run(['taskset','-c','0',*map(str,cmd)],check=True,capture_output=True,text=True);assert not p.stderr,p.stderr
  r=json.loads(p.stdout);r.update(trial=trial,variant=name);rows.append(r);group.append(r)
 assert group[0]['hash']==group[2]['hash']
 assert group[1]['hash']==json.loads((here.parent/'entropy-span/confirm-results.json').read_text())['records'][1]['hash']
 a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
 brackets.append(dict(trial=trial,stock_ms=a,current_ms=b,latency_reduction_percent=100*(1-b/a),throughput_speedup=a/b))
 (here/'results.json').write_text(json.dumps(dict(records=rows,brackets=brackets),indent=2)+'\n');print(brackets[-1],flush=True)
a=statistics.mean(r['stock_ms'] for r in brackets);b=statistics.mean(r['current_ms'] for r in brackets)
summary=dict(stock_ms=a,current_ms=b,saved_ms=a-b,stock_fps=1000/a,current_fps=1000/b,latency_reduction_percent=100*(1-b/a),throughput_speedup=a/b,throughput_increase_percent=100*(a/b-1),brackets=brackets,stock_binary_sha256=hashlib.sha256(stock.read_bytes()).hexdigest(),current_binary_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),method='CPU 0; three stock/current/stock brackets; 1920x1080 4:2:2 capture, 90 preloaded held-out frames; six measured passes after full warmup; loading/allocation/hash/GPU upload/encoding excluded; stock TurboJPEG fast planar plus AVX2 NV12 pack versus selected register-Y/inline-clear/precomputed-span/reduced-UV pipeline; both fast Y, documented UV output difference retained.')
(here/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
