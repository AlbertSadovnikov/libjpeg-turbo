#!/usr/bin/env python3
from pathlib import Path
import subprocess,json,statistics
here=Path(__file__).resolve().parent;work=Path('/tmp/mjpeg-memset-call')
def run(c,**kw):return subprocess.run(list(map(str,c)),check=True,**kw)
flags=['-O3','-DNDEBUG','-std=c++17','-mtune=znver2']
run(['clang++',*flags,'-c',here/'empty.cc','-o',work/'empty.o'])
run(['clang++',*flags,'-c',here/'micro.cc','-o',work/'micro.o'])
run(['clang++','-fuse-ld=gold','-flto=thin',work/'micro.o',work/'empty.o','/tmp/mjpeg-fused-chroma/pgo/libjpeg.a','-o',work/'micro'])
r=run(['taskset','-c','0',work/'micro'],capture_output=True,text=True);assert not r.stderr,r.stderr
x=json.loads(r.stdout);x['kind_names']=['jzero_far -> libc','direct dynamic libc','forced inline 512','guarded inline AVX2','empty opaque call','inline barrier only']
(here/'micro-results.json').write_text(json.dumps(x,indent=2)+'\n')
summary={}
for off in (32,0,1):
 summary[str(off)]={}
 for k,name in enumerate(x['kind_names']):
  v=[r['ns_per_clear'] for r in x['rounds'] if r['offset']==off and r['kind']==k]
  summary[str(off)][name]={'mean_ns':statistics.mean(v),'min_ns':min(v),'max_ns':max(v),'equivalent_ms_per_16200':statistics.mean(v)*16200/1e6}
(here/'micro-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary['32'],indent=2))
