#!/usr/bin/env python3
from pathlib import Path
import json,subprocess,statistics
here=Path(__file__).resolve().parent;root=here.parents[3];work=Path('/tmp/mjpeg-coefficient-cost')
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(frames)==120
fixtures=sorted(Path('/tmp/mjpeg-lut-pipeline/fixtures').glob('*.jpg'));assert len(fixtures)==6
def save(name,x):(here/(name+'.json')).write_text(json.dumps(x,indent=2)+'\n')
def run(binary,*args):
 p=subprocess.run(['taskset','-c','0',str(binary),*map(str,args)],capture_output=True,text=True);p.check_returncode();assert not p.stderr,p.stderr;return json.loads(p.stdout)
check=run(work/'check-variants');check['kind_mapping']={'0':'two SSE2','1':'existing paired','2':'conversion + direct layout','3':'register rewrite'};check['extra_validation']='10000 additional synthetic quantizer tables, every synthetic coefficient pair checked with original and changed table';save('variant-kernels',check)
# Full Clang wrapper compilation changes the existing floating-point UV
# contract in its control. Audit its generated code, but do not time it as an
# output-preserving candidate against the retained GCC fusion wrapper.
ref=run('/tmp/mjpeg-paired-idct/paired','validate',*frames)
clang=run(work/'clang++-control','validate',*frames)
save('compiler-contract',dict(reference=ref,clang_control=clang,clang_matches=clang==ref,clang_admitted_to_timing=False))
validation={}
for label,inputs in [('capture',frames),*[(p.stem,[p]) for p in fixtures]]:
 ref=run('/tmp/mjpeg-paired-idct/paired','validate',*inputs)
 for cc in ('g++',):
  for name in ('control','layout','registers'):
   got=run(work/(cc+'-'+name),'validate',*inputs);assert got==ref,(label,cc,name)
 validation[label]=ref
save('variant-validation',dict(cases=validation,matched_variants=['g++-'+n for n in ('control','layout','registers')]))
print('GCC wrapper: all captures and fixtures match, both IDCT modes and padding; Clang control excluded for changed UV bytes.',flush=True)
records=[];brackets=[]
for trial in range(5):
 for cc in ('g++',):
  for candidate in (('layout','registers') if trial%2==0 else ('registers','layout')):
   rows=[]
   for name in ('control',candidate,'control'):
    row=run(work/(cc+'-'+name),'fast',2,3,*frames[30:]);row.update(trial=trial,compiler=cc,variant=name,candidate=candidate);rows.append(row);records.append(row)
   assert len({r['hash'] for r in rows})==1
   control=statistics.mean([rows[0]['mean_ms'],rows[2]['mean_ms']]);value=rows[1]['mean_ms']
   brackets.append(dict(trial=trial,compiler=cc,variant=candidate,control_ms=control,candidate_ms=value,change_percent=100*(value/control-1)))
   save('variant-results',dict(records=records,brackets=brackets));print(brackets[-1],flush=True)
summary={}
for cc in ('g++',):
 summary[cc]={}
 for name in ('layout','registers'):
  rows=[r for r in brackets if r['compiler']==cc and r['variant']==name]
  a=statistics.mean(r['control_ms'] for r in rows);b=statistics.mean(r['candidate_ms'] for r in rows)
  summary[cc][name]=dict(control_ms=a,candidate_ms=b,change_percent=100*(b/a-1),brackets=rows)
save('variant-summary',dict(cases=summary,method='CPU 0; five control/candidate/control brackets per admitted candidate; GCC wrapper retained for output equality, Clang assembly audited only; 90 preloaded held-out frames, 3 passes after full warmup; same retained codec archives and reduced UV kernel; controls use existing paired Y kernel; only wrappers and kernel objects change'))
print(json.dumps(summary,indent=2))
